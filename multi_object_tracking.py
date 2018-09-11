# import the necessary packages
from imutils.video import VideoStream
from imutils.video import FileVideoStream
from imutils.video import FPS
import argparse
import imutils
import time
import cv2
from lnglat_homography import RealWorldCoordinates
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from datetime import datetime, timezone
import os
import numpy as np
import multiprocessing
from multiprocessing import Queue, Pool
from queue import PriorityQueue
from queue import Empty

import requests
import boto3
import botocore
from PIL import Image
import json
import sys
from threading import Thread
import detection_visualization_util

# Use a service account
cred = credentials.Certificate(os.environ['FIREBASE_CREDENTIALS'])
firebase_admin.initialize_app(cred)

gl_db = firestore.client()
gl_routes = gl_db.collection(u'routes')
gl_nodes = gl_db.collection(u'nodes')

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("--display", type=int, default=1,
                help="whether or not to display frames in UI")
ap.add_argument("--video", type=str,
                help="path to input video file")
ap.add_argument("--picamera", type=int, default=-1,
                help="whether or not the Raspberry Pi camera should be used")
ap.add_argument("--tracker", type=str, default="mosse",
                help="OpenCV object tracker type")
ap.add_argument("--num_workers", type=int, default=5,
                help="Number of Workers")
args = vars(ap.parse_args())

# initialize a dictionary that maps strings to their corresponding
# OpenCV object tracker implementations
OPENCV_OBJECT_TRACKERS = {
    "csrt": cv2.TrackerCSRT_create,
    "kcf": cv2.TrackerKCF_create,
    "boosting": cv2.TrackerBoosting_create,
    "mil": cv2.TrackerMIL_create,
    "tld": cv2.TrackerTLD_create,
    "medianflow": cv2.TrackerMedianFlow_create,
    "mosse": cv2.TrackerMOSSE_create
}
 
# initialize OpenCV's special multi-object tracker
trackers = cv2.MultiTracker_create()


s3_res = boto3.resource('s3')
s3_bucket = s3_res.Bucket('grassland-images')

lambda_url = os.environ['LAMBDA_DETECTION_URL']

def get_detections_error_callback(the_exception):
    print("get_detections_error_callback called")
    print(the_exception)

def get_detections(frame_number,frame):
    try:
        image = Image.fromarray(frame) # Remember Opencv images are in 'BGR'
        file_name_ext = 'frame_'+str(frame_number)+'.jpg'
        file_path = '/tmp/'+file_name_ext

        image.save(file_path)

        print("Uploading image file to s3")
        image_start_time = time.time()
        s3_bucket.upload_file(file_path, file_name_ext)
        print("S3 Upload Time:", time.time()-image_start_time)

        print("Making request on lambda")
        #print(lambda_url+"?bucket=grassland-images&key="+file_name_ext)
        response = requests.get(lambda_url+"?bucket=grassland-images&key="+file_name_ext)

        end_time = time.time()

        print("ROUND TRIP TIME:", end_time-image_start_time)

        response_dict = json.loads(response.text)


        output_dict = response_dict['prediction_result']

        detection_boxes = np.array(output_dict['detection_boxes'])
        detection_scores = np.array(output_dict['detection_scores'])
        detection_classes = np.array(output_dict['detection_classes'])
        output_dict['detection_boxes'] = detection_boxes
        output_dict['detection_scores'] = detection_scores
        output_dict['detection_classes'] = detection_classes


        return ( frame_number, {"detected": 1, "frame": frame, "output_dict": output_dict} )
    except:
        import traceback
        traceback.print_exc()
        
        raise # Without this, the regular callback of apply_async will be called

        
def add_to_p_queue(detected_frame_tuple):
    try:
        print("Adding detection to p_queue")
        p_queue.put(detected_frame_tuple)
    except:
        import traceback
        traceback.print_exc()
        raise
        


# if a video path was not supplied, grab the reference to the web cam
if not args.get("video", False):
    print("[INFO] starting video stream...")
    vs = VideoStream(usePiCamera=args["picamera"] > 0).start() # Default to PiCamera
    
 
# otherwise, grab a reference to the video file
else:
    #vs = cv2.VideoCapture(args["video"])
    vs = FileVideoStream(args["video"], queueSize=30).start()

    # loop over frames from the video stream


    
rw = RealWorldCoordinates()
rw.set_transform(dynamic=True, gl_nodes=gl_nodes)


first_frame_detected = False
if args["display"] == 1:
    display = True
else:
    display = False
    
run_worker = False

count_read_frame = 0
count_write_frame = 1

                
count = 0

frame_dimensions_set = False
last_frame = np.array([])
#frame_number = 0
start = time.time()
update_frames = True


lambda_wakeup_duration = 0

print("Sending Wakeup Ping to Lambda function")
requests.get(lambda_url)
print("Waiting "+str(lambda_wakeup_duration)+" seconds for function to wake up...")
time.sleep(lambda_wakeup_duration)

main_fps = FPS().start()
worker_fps = FPS().start()

def worker():
    global p_queue
    global worker_fps
    try:
        frame_loop_count = 0
        while run_worker:
            # Pull first/next frame tuple from p_queue
            #queue_get_start_time = time.time()
            try:
                frame_number, frame_dict = p_queue.get(timeout=20)
            except:
                # If there are no more frames being put into p_queue, stop the thread
                print("No More Frames In p_queue")
                return
            
            #print("queue_get_start_time Time:", time.time()-queue_get_start_time)

            if frame_number > frame_loop_count:
                p_queue.task_done() 
                '''
                This tracking loop has outpaced our actual frames because of our "detections" bottleneck
                Since we're adding the same frame back to p_queue again, an act which increases the task 
                count, calling .task_done() ensures the count of unfinished tasks does not exceed the 
                number of actual frames or else .join() will never stop blocking because it assumes
                that there are more tasks/frames to complete than we actually have. 
                https://docs.python.org/3.4/library/queue.html#queue.Queue.join 
                '''
                p_queue.put((frame_number, frame_dict))
            else:
                frame_loop_count += 1
                this_frame = frame_dict["frame"]
                if frame_dict.get("detected") == 1:

                    # (re-)initialize OpenCV's special multi-object tracker
                    try:
                        trackers.clear()
                    except:
                        pass
                    
                    trackers = cv2.MultiTracker_create() # Or we end up with multiple boxes on same object

                    output_dict = frame_dict.get("output_dict")
                    

                    tracker_boxes = detection_visualization_util.get_bounding_boxes_for_image_array(
                        this_frame,
                        output_dict['detection_boxes'],
                        output_dict['detection_classes'],
                        output_dict['detection_scores'],
                        instance_masks=output_dict.get('detection_masks'),
                        use_normalized_coordinates=True,
                        line_thickness=1,
                        skip_scores=True,
                        skip_labels=True
                    )


                    manual = False

                    if manual:
                        bbox = cv2.selectROI("Frame", this_frame, fromCenter=False, showCrosshair=True)

                        tracker_boxes = []
                        tracker_boxes.append(bbox)
                    else:
                        for idx, bbox in enumerate(tracker_boxes):
                            
                            xmin, ymin, xmax, ymax = bbox
                        
                            tracker_boxes[idx] = (xmin, ymin, xmax-xmin, ymax-ymin)


                        
                    #tracker = OPENCV_OBJECT_TRACKERS[args["tracker"]]()
                    #ok = tracker.init(this_frame, bbox)
                        
                    # if ok:
                    #     print("New tracking box initialized")

                    for bbox in tracker_boxes:
                        tracker = OPENCV_OBJECT_TRACKERS[args["tracker"]]()
                        trackers.add(tracker, this_frame, bbox)
                    

                    # -> if frame_dict.get("detected") == 1:
                    
                else:
                    
                    # grab the updated bounding box coordinates (if any) for each
                    # object that is being tracked

                    #ok, bbox = tracker.update(this_frame)
                    ok, tracker_boxes = trackers.update(this_frame)

                    
                    if not ok:
                        # Tracking failure
                        #print("----- OBJECT TRACKER NOT UPDATING !! -----")
                        if display:
                            cv2.putText(this_frame, "Tracking failure detected", (100,80), cv2.FONT_HERSHEY_SIMPLEX, 0.75,(0,0,255),2)
                    else:
                        # Tracking success
                        if manual:
                            tracker_boxes = []
                            tracker_boxes.append(bbox)
                        
                    
                    # -> if frame_dict.get("detected") == 1: else:
                    
                if display:
                    # Draw tracker boxes on frame
                    for bbox in tracker_boxes:
                        #(xmin, xmax, ymin, ymax) = [int(v) for v in box]
                        #cv2.rectangle(this_frame, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2, 1)

                        p1 = (int(bbox[0]), int(bbox[1]))
                        p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
                        cv2.rectangle(this_frame, p1, p2, (0,255,0), 2)

                    
                    # show the output frame
                    cv2.imshow("Frame", this_frame)
                    key = cv2.waitKey(1) & 0xFF


                    # if the 's' key is selected, we are going to "select" a bounding
                    # box to track
                    if key == ord("s"):
                        # select the bounding box of the object we want to track (make
                        # sure you press ENTER or SPACE after selecting the ROI)
                        box = cv2.selectROI("Frame", this_frame, fromCenter=False, showCrosshair=True)

                        # create a new object tracker for the bounding box and add it
                        # to our multi-object tracker
                        tracker = OPENCV_OBJECT_TRACKERS[args["tracker"]]()

                        trackers.add(tracker, frame, box)


                    # if the `q` key was pressed, break from the loop
                    elif key == ord("q"):
                        break


                worker_fps.update()

                # Let the system know the task is done
                p_queue.task_done()
                    
                # -> if frame_number > frame_loop_count: else:

            
            # -> while True:
                
            
    except:
        import traceback
        traceback.print_exc()

        raise



p_queue = PriorityQueue()
pool = Pool(multiprocessing.cpu_count())

try:
    while True:

        # grab the current frame, then handle if we are using a
        # VideoStream or VideoCapture object
        if args.get("video", False):
            if vs.Q.empty():
                frame = None
            else:
                frame = vs.read()
        else:
            frame = vs.read()
            

        # check to see if we have reached the end of the stream
        if frame is None:
            print("REACHED END OF CAMERA/VIDEO STREAM")
            break

        # If we use threading (imutils.video.VideoStream/FileVideoStream), then we don't want to process the same frame twice
        if frame is not None and not np.array_equal(last_frame, frame):
            last_frame = frame

            #frame_number += 1

            frame = imutils.resize(frame, width=800)


            if not frame_dimensions_set: # Important For Homography to real world coordinates (lat/long)
                height, width, channels = frame.shape
                # Tell Grassland what the frame dimensions are for camera calibration
                gl_nodes.document('0').update({u'tracking_frame': {u'width': width, u'height': height}})

                frame_dimensions_set = True



            current_main_fps = main_fps._numFrames / (datetime.now() - main_fps._start).total_seconds()

            main_fps_divisor = int(current_main_fps * 4)
            if main_fps_divisor == 0:
                main_fps_divisor = 1

            if main_fps._numFrames == 0 or main_fps._numFrames % main_fps_divisor == 0:
                # Run asynchronous object detection on frame


                #print("about to call apply_async")
                pool.apply_async(func=get_detections, args=(main_fps._numFrames, frame), callback=add_to_p_queue, error_callback=get_detections_error_callback)

                #print("called apply_async")

                print("p_queue size")
                print(p_queue.qsize())

                if main_fps._numFrames == 0:
                    first_frame_detected = True

            else:
                # store frame in priority queue
                p_queue.put((main_fps._numFrames, {"detected": 0, "frame": frame}))



            # update the FPS counter
            main_fps.update()


            
            # -> if frame is not None and not np.array_equal(last_frame, frame):
        

        
        
        if first_frame_detected and not run_worker:
            print("about to start")
            run_worker = True

            t = Thread(target=worker, args=())
            t.daemon = True
            t.start()

            #pool.apply_async(worker) # Doesn't work. Program freezes




        count += 1



except:
    import traceback
    traceback.print_exc()
    
finally:    

    print("Finishing up items in p_queue")
    p_queue.join()
    print("CLOSING POOL")
    pool.close()
    print("TERMINATING POOL")
    pool.terminate()

    pool.join()

    vs.stop()
    # if we are using a webcam, release the pointer
    #if not args.get("video", False):
       

    # otherwise, release the file pointer
    #else:
    #    vs.release()

    # close all windows
    print("CLOSING CV WINDOWS")
    cv2.destroyAllWindows()

    # stop the timer and display FPS information
    main_fps.stop()
    worker_fps.stop()
    print("[INFO] elasped time: {:.2f}".format(main_fps.elapsed()))
    print("[INFO] approx. Main FPS: {:.2f}".format(main_fps.fps()))
    print("[INFO] approx. Worker FPS: {:.2f}".format(worker_fps.fps()))

