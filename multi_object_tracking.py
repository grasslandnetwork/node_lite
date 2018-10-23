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
from random import randint
import concurrent.futures
from pyimagesearch.centroidtracker import CentroidTracker
from pyimagesearch.trackableobject import TrackableObject

node_id = os.environ['NODE_ID']

# Use a service account
cred = credentials.Certificate(os.environ['FIREBASE_CREDENTIALS'])
firebase_admin.initialize_app(cred)

gl_db = firestore.client()
gl_nodes = gl_db.collection(u'nodes')

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("--display", type=int, default=1,
                help="whether or not to display frames in UI")
ap.add_argument("--video", type=str,
                help="path to input video file")
ap.add_argument("--picamera", type=int, default=-1,
                help="whether or not the Raspberry Pi camera should be used")
ap.add_argument("--rotation", type=int, default=0,
                help="Sets Rasperry Pi camera's clockwise rotation. Valid values are 0, 90, 180, and 270.")
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

'''
Good ratio for live camera
detection_frame_width = 800,tracking_frame_width = 500,delta_thresh = 4,min_area = 20
'''

frame_ratio = 1080/1920
detection_frame_width = 1280
tracking_frame_width = 500
delta_thresh = int(tracking_frame_width/125)
min_area = int(tracking_frame_width/25)


s3_res = boto3.resource('s3')
s3_bucket = s3_res.Bucket('grassland-images')

lambda_url = os.environ['LAMBDA_DETECTION_URL']

tracklets_queue_max = 100
o_queue_max = 80
p_queue_max = 300

tracklets_queue = Queue() # tracklets queue    
i_queue = Queue() # input queue    
o_queue = Queue(maxsize=o_queue_max) # output queue
p_queue = PriorityQueue(maxsize=p_queue_max) # priority queue


def delete_from_s3(s3_bucket, file_name_ext):
    try:
        s3_bucket.delete_objects(
            Delete={
                'Objects': [
                    {
                        'Key': file_name_ext
                    }
                ]
            }
        )
    except:
        import traceback
        traceback.print_exc()


                
def get_detections_error_callback(the_exception):
    print("get_detections_error_callback called")
    print(the_exception)

def get_detections(frame_number, frame, frame_timestamp, no_callback=False):    
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


        detected_frame_tuple = ( frame_number, {"detected": 1, "frame": frame, "frame_timestamp": frame_timestamp, "output_dict": output_dict} )
        if no_callback:
            add_to_o_queue(detected_frame_tuple)
            delete_from_s3(s3_bucket, file_name_ext)
        else:
            delete_from_s3(s3_bucket, file_name_ext)
            return detected_frame_tuple


    except KeyboardInterrupt:
        import traceback
        traceback.print_exc()
        raise                
    except:
        import traceback
        traceback.print_exc()
        
        #raise # Without this raise, the regular callback of apply_async will be called

        
def add_to_o_queue(detected_frame_tuple):
    try:
        if o_queue.full():
            print("o_queue FULL")
            print("-------PROGRAM STOPPED UNTIL o_queue DRAINED INTO p_queue-----")
            
        #if not o_queue.full():
        #    print("Adding detection to o_queue")
        #    print("o_queue size")
        #    print(o_queue.qsize())

        # Change detected frame back to size for tracking
        frame_number, frame_dict = detected_frame_tuple
        frame = frame_dict['frame']
        frame = imutils.resize(frame, width=tracking_frame_width)
        frame_dict['frame'] = frame
        detected_frame_tuple = (frame_number, frame_dict)

        o_queue.put(detected_frame_tuple)
        #else:
        #    print("o_queue full")
    except:
        import traceback
        traceback.print_exc()
        raise
        



# if a video path was not supplied, grab the reference to the web cam
if not args.get("video", False):
    framerate = 30
        
    print("[INFO] starting video stream...")    
    #vs = VideoStream(usePiCamera=args["picamera"], resolution=(800, 464), framerate=framerate).start() # Default to PiCamera
    vs = VideoStream(usePiCamera=args["picamera"], resolution=(detection_frame_width, int(detection_frame_width*frame_ratio)), framerate=framerate).start() # Default to PiCamera
    print("[INFO] Warming up camera...")
    time.sleep(3)
    
    if args["picamera"] == 1 or args["picamera"] == True:
        vs.camera.rotation = args["rotation"]
    
    # otherwise, grab a reference to the video file
else:
    framerate = 30
    #vs = cv2.VideoCapture(args["video"])
    vs = FileVideoStream(args["video"], queueSize=15).start()

    # loop over frames from the video stream


    
'''
Here we calculate and set the linear map (transformation matrix) that we use to turn the pixel coordinates of the objects on the frame into their corresponding lat/lng coordinates in the real world. It's a computationally expensive calculation and requires inputs from the camera's calibration (frame of reference in the real world) so we do it once here instead of everytime we need to do a transformation from pixels to lat/lng
'''
rw = RealWorldCoordinates()
rw.set_transform() 



first_frame_detected = False
if args["display"] == 1:
    display = True
else:
    display = False
    
run_tracking_loop = False

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

gl_api_endpoint = os.environ['GRASSLAND_API_ENDPOINT']
def post_tracklet(tracklet_dict):
    post_tracklet_start_time = time.time()

    print("Making request on lambda")
    response = requests.post(gl_api_endpoint+"tracklets_create", json=tracklet_dict)

    end_time = time.time()

    print("TRACKLET ROUND TRIP TIME:", end_time-post_tracklet_start_time)

        
def tracklets_loop():
    try:
        print("STARTING TRACKLETS_LOOP")
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            while True:

                try:
                    if not tracklets_queue.empty():

                        tracklet_dict = tracklets_queue.get(block=False)

                        before_executor = time.time()
                        executor.submit(post_tracklet, tracklet_dict)
                        print("Tracklet Executor Time:", time.time()-before_executor)

                    else:
                        try:
                            if int((datetime.now() - idle_since).total_seconds()) > 40:
                                idle_since = datetime.now()
                                print("no tracklets_queue items for tracklets loop .................")
                        except:
                            idle_since = datetime.now()



                except Empty:
                    print("tracklets_queue empty error")                        
                except KeyboardInterrupt:
                    import traceback
                    traceback.print_exc()
                    raise                
                except:
                    import traceback
                    traceback.print_exc()

    except KeyboardInterrupt:
        import traceback
        traceback.print_exc()
        raise                
    except:
        import traceback
        traceback.print_exc()


def tracking_loop():
    try:
        print("STARTING TRACKING_LOOP")
        #global tracking_loop_fps
        tracking_loop_fps = FPS().start()
        
        frame_loop_count = 0
        avg = None
        tracker_boxes = []
        track_centroids = True

        ct = CentroidTracker(maxDisappeared=10, maxDistance=tracking_frame_width/20)
        trackableObjects = {}
        
        
        #while run_tracking_loop:
        while True:
            # Pull first/next frame tuple from p_queue
            #queue_get_start_time = time.time()

            if tracking_loop_fps._numFrames % 70 == 0 and not tracking_loop_fps._numFrames == 0:
                current_tracking_loop_fps = tracking_loop_fps._numFrames / (datetime.now() - tracking_loop_fps._start).total_seconds()
                print("[INFO] approx. Tracking_Loop Running FPS: {:.2f}".format(current_tracking_loop_fps))

                
            try:
                if p_queue.full():
                    print("p_queue FULL .......................................................")
                    # Then we'll need to drop the next frame from the stack
                    frame_number, frame_dict = p_queue.get()

                    frame_loop_count = frame_number + 1 # Since we're skipping a frame, we'll need to make sure frame_loop_count catches up to the next frame_number 
                    continue # Start loop again
                else:
                    
                    p_queue.put(o_queue.get(timeout=20)) # Bring frames from shared output queue into priority queue so they can be used in order
                    frame_number, frame_dict = p_queue.get(timeout=20)
                    
            except:
                # If there are no more frames being put into p_queue, stop the thread
                print("No More Frames In p_queue")
                tracking_loop_fps.stop()
                print("[INFO] approx. Tracking_Loop FPS: {:.2f}".format(tracking_loop_fps.fps()))
                return
            
            #print("queue_get_start_time Time:", time.time()-queue_get_start_time)

            try:
                if int((datetime.now() - running_notice_since).total_seconds()) > 40:
                    running_notice_since = datetime.now()
                    print("tracking_loop still running ...")
            except:
                running_notice_since = datetime.now()


            # if p_queue.qsize() > 70:
            #     print("p_queue size")
            #     print(p_queue.qsize())

            if frame_number > frame_loop_count:
                try:
                    if int((datetime.now() - frame_number_high_notice_since).total_seconds()) > 10:
                        frame_number_high_notice_since = datetime.now()
                        print("frame number too high ...")
                except:
                    frame_number_high_notice_since = datetime.now()

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
                frame_timestamp = frame_dict["frame_timestamp"]
                if frame_dict.get("detected") == 1:

                    # (re-)initialize OpenCV's special multi-object tracker
                    # try:
                    #     trackers.clear()
                    # except:
                    #     pass
                    
                    #trackers = cv2.MultiTracker_create() # Or we end up with multiple boxes on same object

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


                    #print(tracker_boxes)
                    # Remove items from tracker_boxes that aren't
                    # a person, bicycle, car, motorcycle, bus or truck
                    # tracker_boxes_to_delete = []
                    # for idx in range(len(tracker_boxes)):
                    #     if tracker_boxes[idx][4] not in [1, 2, 3, 4, 6, 8]:
                    #         tracker_boxes_to_delete.append(idx)


                    # for tracker_box_idx in tracker_boxes_to_delete:
                    #         try:
                    #             del tracker_boxes[tracker_box_idx]
                    #         except:
                    #             print(tracker_boxes)
                    #             print(idx)

                            

                    manual = False
                    if display:
                        colors = [] # For display when testing consistent track association
                        
                    if manual:
                        bbox = cv2.selectROI("Frame", this_frame, fromCenter=False, showCrosshair=True)

                        tracker_boxes = []
                        tracker_boxes.append(bbox)
                    else:
                        if track_centroids:
                            rects = []
                        
                        for idx, bbox in enumerate(tracker_boxes):
                            
                            xmin, ymin, xmax, ymax, detection_class_id = bbox

                            tracker_boxes[idx] = (xmin, ymin, xmax-xmin, ymax-ymin)

                            
                            if track_centroids:
                                rects.append((xmin, ymin, xmax, ymax, frame_timestamp, detection_class_id))
                        
                            if display:
                                colors.append((randint(0, 255), randint(0, 255), randint(0, 255)))


                    '''
                    Use object detection to identify the objects that
                    we've been tracking though just motion detection,
                    contours and centroids. 
                    Record those tracklets that belong to objects we want
                    '''
                    if track_centroids:

                        # use the centroid tracker to associate the (1) old object
                        # centroids with (2) the object detections
                        objects = ct.update(rects, True)

                        # loop over the tracked objects to add them to objectsPositions and to trackableObjects
                        objectsPositions = []
                        for (objectID, (centroid, boxoid)) in objects.items():

                            # Calculate bottom center pixel coordinates
                            #bottom_center_x = (boxoid[0] + boxoid[2]) / 2
                            bottom_center_x = centroid[0]
                            bottom_center_y = boxoid[3]


                            objectsPositions.append({
                                "tracklet_id": objectID,
                                "node_id": node_id,
                                "bbox_rw_coord": {
                                    "btm_left": rw.coord(boxoid[0], boxoid[3]),
                                    "btm_right": rw.coord(boxoid[2], boxoid[3]),
                                    "btm_center": rw.coord(bottom_center_x, bottom_center_y)
                                },
                                "frame_timestamp": boxoid[4],
                                "detection_class_id": boxoid[5]
                            })

                                
                            # check to see if a trackable object exists for the current
                            # object ID
                            to = trackableObjects.get(objectID, None)

                            # if there is no existing trackable object, create one
                            if to is None:
                                to = TrackableObject(objectID, centroid, boxoid)

                            # otherwise, there is a trackable object so we can utilize it
                            # to determine direction
                            else:
                                # the difference between the y-coordinate of the *current*
                                # centroid and the mean of *previous* centroids will tell
                                # us in which direction the object is moving (negative for
                                # 'up' and positive for 'down')
                                y = [c[1] for c in to.centroids]
                                direction = centroid[1] - np.mean(y)
                                to.centroids.append(centroid)
                                to.boxoids.append(boxoid)


                            # store the trackable object in our dictionary
                            trackableObjects[objectID] = to


                            
                        ## Put tracklet tip data in queue via a separate process/thread
                        ## To update their position in database
                        tracklets_queue.put({ "tracklets": objectsPositions })                                

                        

                        # For all the objects in trackableObjects

                        # After updating, if object has been marked as "disappeared"
                        # then add it to disappeared_objects list
                        disappeared_objects = []
                        for object_id, trackableObject in trackableObjects.items():
                                
                            # If the object has disappeared, remove it from trackableObjects
                            if not ct.objects.get(object_id, False): 
                                disappeared_objects.append(object_id)



                        
                        # Remove "disappeared" objects from trackableObjects
                        for object_id in disappeared_objects:
                            # print('DELETE '+str(object_id)+' OBJECT')
                            del trackableObjects[object_id]


                            
                        # -> if track_centroids
                    

                    #tracker = OPENCV_OBJECT_TRACKERS[args["tracker"]]()
                    #ok = tracker.init(this_frame, bbox)
                        
                    # if ok:
                    #     print("New tracking box initialized")

                    # for bbox in tracker_boxes:
                    #     tracker = OPENCV_OBJECT_TRACKERS[args["tracker"]]()
                    #     trackers.add(tracker, this_frame, bbox)
                    

                    # -> if frame_dict.get("detected") == 1:
                    
                # else:

                #     if frame_number % (framerate - 14) == 0:
                        # grab the updated bounding box coordinates (if any) for each
                        # object that is being tracked

                        #ok, bbox = tracker.update(this_frame)
                        #ok, tracker_boxes = trackers.update(this_frame)


                        # if not ok:
                        #     # Tracking failure
                        #     #print("----- OBJECT TRACKER NOT UPDATING !! -----")
                        #     if display:
                        #         cv2.putText(this_frame, "Tracking failure detected", (100,80), cv2.FONT_HERSHEY_SIMPLEX, 0.75,(0,0,255),2)
                        # else:
                        #     # Tracking success
                        #     if manual:
                        #         tracker_boxes = []
                        #         tracker_boxes.append(bbox)

                    
                    # -> if frame_dict.get("detected") == 1: else:

                    
                gray = cv2.cvtColor(this_frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)

                # if the average frame is None, initialize it
                if avg is None:
                    print("[INFO] starting background model...")
                    avg = gray.copy().astype("float")
                    #rawCapture.truncate(0)
                    #continue
                    cnts = []

                else:
                    # accumulate the weighted average between the current frame and
                    # previous frames, then compute the difference between the current
                    # frame and running average
                    cv2.accumulateWeighted(gray, avg, 0.5)
                    frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(avg))

                    kernel = np.ones((5,5),np.uint8)
                    # threshold the delta image, dilate the thresholded image to fill
                    # in holes, then find contours on thresholded image
                    thresh = cv2.threshold(frameDelta, delta_thresh, 255,
                            cv2.THRESH_BINARY)[1]
                    #thresh = cv2.dilate(thresh, None, iterations=2)
                    thresh = cv2.dilate(thresh, kernel, iterations=2)
                    cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
                            cv2.CHAIN_APPROX_SIMPLE)
                    cnts = cnts[0] if imutils.is_cv2() else cnts[1]

    

                if track_centroids:
                    rects = []

                # loop over the contours
                for c in cnts:
                    # if the contour is too small, ignore it
                    if cv2.contourArea(c) < min_area:
                        continue

                    (x, y, w, h) = cv2.boundingRect(c)
                    
                    if display:
                        # compute the bounding box for the contour, draw it on the frame,
                        # and update the text
                        cv2.rectangle(this_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)


                    startX = x
                    startY = y
                    endX = x + w
                    endY = y + h

                    if track_centroids:
                        # add the bounding box coordinates to the rectangles list
                        # put 0 in detection_class_id section since we don't have a detection yet
                        rects.append((startX, startY, endX, endY, frame_timestamp, 0))


                if track_centroids:
                    # use the centroid tracker to associate the (1) old object
                    # centroids with (2) the newly computed object centroids
                    objects = ct.update(rects)

                    # loop over the tracked objects to add them to objectsPositions and to trackableObjects
                    objectsPositions = []
                    for (objectID, (centroid, boxoid)) in objects.items():

                        # Calculate bottom center pixel coordinates
                        #bottom_center_x = (boxoid[0] + boxoid[2]) / 2
                        bottom_center_x = centroid[0]
                        bottom_center_y = boxoid[3]


                        objectsPositions.append({
                            "tracklet_id": objectID,
                            "node_id": node_id,
                            "bbox_rw_coord": {
                                "btm_left": rw.coord(boxoid[0], boxoid[3]),
                                "btm_right": rw.coord(boxoid[2], boxoid[3]),
                                "btm_center": rw.coord(bottom_center_x, bottom_center_y)
                            },
                            "frame_timestamp": boxoid[4],
                            "detection_class_id": boxoid[5]
                        })

                            
                        # check to see if a trackable object exists for the current
                        # object ID
                        to = trackableObjects.get(objectID, None)

                        # if there is no existing trackable object, create one
                        if to is None:
                            to = TrackableObject(objectID, centroid, boxoid)

                        # otherwise, there is a trackable object so we can utilize it
                        # to determine direction
                        else:
                            # the difference between the y-coordinate of the *current*
                            # centroid and the mean of *previous* centroids will tell
                            # us in which direction the object is moving (negative for
                            # 'up' and positive for 'down')
                            y = [c[1] for c in to.centroids]
                            direction = centroid[1] - np.mean(y)
                            to.centroids.append(centroid)
                            to.boxoids.append(boxoid)

                            # # check to see if the object has been counted or not
                            # if not to.counted:
                            #     # if the direction is negative (indicating the object
                            #     # is moving up) AND the centroid is above the center
                            #     # line, count the object
                            #     if direction < 0 and centroid[1] < H // 2:
                            #         totalUp += 1
                            #         to.counted = True

                            #     # if the direction is positive (indicating the object
                            #     # is moving down) AND the centroid is below the
                            #     # center line, count the object
                            #     elif direction > 0 and centroid[1] > H // 2:
                            #         totalDown += 1
                            #         to.counted = True

                        # store the trackable object in our dictionary
                        trackableObjects[objectID] = to

                        if display:
                            # draw both the ID of the object and the centroid of the
                            # object on the output frame
                            text = "ID {}".format(objectID[0:3])
                            cv2.putText(this_frame, text, (centroid[0] - 10, centroid[1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                            cv2.circle(this_frame, (centroid[0], centroid[1]), 4, (0, 255, 0), -1)


                            
                    ## Put tracklet tip data in queue via a separate process/thread
                    ## To update their position in database
                    tracklets_queue.put({ "tracklets": objectsPositions })                                

                    
                    # -> if track_centroids

                    
                if display:
                    # Draw tracker boxes on frame
                    for idx, bbox in enumerate(tracker_boxes):
                        #(xmin, xmax, ymin, ymax) = [int(v) for v in box]
                        #cv2.rectangle(this_frame, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2, 1)

                        p1 = (int(bbox[0]), int(bbox[1]))
                        p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
                        cv2.rectangle(this_frame, p1, p2, colors[idx], 2)

                    
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


                tracking_loop_fps.update()

                # Let the system know the task is done
                p_queue.task_done()
                    
                # -> if frame_number > frame_loop_count: else:

            
            # -> while True:
                
            
    except:
        import traceback
        traceback.print_exc()

        raise


def detection_loop():
    try:
        print("STARTING DETECTION_LOOP")
        while True:

            try:
                if not i_queue.empty():

                    frame_number, frame, frame_timestamp = i_queue.get(block=False)
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        #if not o_queue.full(): # If o_queue is full the tracker isn't moving fast enough and to avoid memory problems, we'll just drop frames
                        #before_executor = time.time()
                        executor.submit(get_detections, frame_number, frame, frame_timestamp, no_callback=True)
                        #print("Executor Time:", time.time()-before_executor)

                else:
                    try:
                        if int((datetime.now() - idle_since).total_seconds()) > 40:
                            idle_since = datetime.now()
                            print("no i_queue items for detection loop .................")
                    except:
                        idle_since = datetime.now()

                        

            except Empty:
                print("i_queue empty error")                        
            except KeyboardInterrupt:
                import traceback
                traceback.print_exc()
                raise                
            except:
                import traceback
                traceback.print_exc()

    except KeyboardInterrupt:
        import traceback
        traceback.print_exc()
        raise                
    except:
        import traceback
        traceback.print_exc()



def o_queue_exceeds_safe_threshold():
    return o_queue.qsize() > int(o_queue_max *0.9)

    
dl = multiprocessing.Process(target=detection_loop)
dl.daemon = True
dl.start()

tsl = multiprocessing.Process(target=tracklets_loop)
tsl.daemon = True
tsl.start()

#pool = Pool(1, detection_loop)
#pool.apply_async(func=detection_loop, args=())

run_feed_loop = True
try:
    main_fps = FPS().start()
    new_framerate = framerate
    while run_feed_loop:
        
        feed_loop_start_time = time.time()
        
        # grab the current frame, then handle if we are using a
        # VideoStream or VideoCapture object
        if args.get("video", False):
            if vs.Q.empty():
                frame = None
            else:
                frame = vs.read()
        else:
            frame = vs.read()

        # Set frame_timestamp in milliseconds    
        frame_timestamp = round( datetime.timestamp(datetime.now(timezone.utc)) * 1000 )

        # check to see if we have reached the end of the stream
        if frame is None:
            print("REACHED END OF CAMERA/VIDEO STREAM")
            break

        # If we use threading (imutils.video.VideoStream/FileVideoStream), then we don't want to process the same frame twice
        if frame is not None and not np.array_equal(last_frame, frame):
            last_frame = frame

            #frame_number += 1

            large_frame = imutils.resize(frame, width=detection_frame_width)
            frame = imutils.resize(frame, width=tracking_frame_width)


            if not frame_dimensions_set: # Important For Homography to real world coordinates (lat/long)
                height, width, channels = frame.shape
                # Tell Grassland what the frame dimensions are for camera calibration
                rw.calibration['tracking_frame'] = {'height': height, 'width': width}
                rw.calibration_update()
                
                frame_dimensions_set = True



            # current_main_fps = main_fps._numFrames / (datetime.now() - main_fps._start).total_seconds()
            # main_fps_divisor = int(current_main_fps * 4)
            # if main_fps_divisor == 0:
            #     main_fps_divisor = 1
            #if main_fps._numFrames == 0 or main_fps._numFrames % main_fps_divisor == 0:


            if main_fps._numFrames == 0 or (datetime.now() - last_i_queue_put).total_seconds() > 3:
                
             
                # Put frame in i_queue to wait for asynchronous object detection
                if not o_queue_exceeds_safe_threshold(): # Since all extant i_queue frames eventually go into o_queue and if o_queue exceeds maxsize, program will stop
                    #print("Putting frame in i_queue")
                    i_queue.put((main_fps._numFrames, large_frame, frame_timestamp))
                    
                    if main_fps._numFrames == 0:
                        first_frame_detected = True

                    main_fps.update()
                else:
                    try:
                        if int((datetime.now() - i_queue_notice_since).total_seconds()) > 40:
                            i_queue_notice_since = datetime.now()
                            print("o_queue 90% full ...")
                            print("...Can't add new frame to i_queue")
                    except:
                        i_queue_notice_since = datetime.now()

                    

                # print("i_queue size")
                # print(i_queue.qsize())

                last_i_queue_put = datetime.now()

                # if i_queue.qsize() > 10:
                #     print("i_queue size too large. Starting detection_loop again")
                #     dl.run()


                #import pdb; pdb.set_trace()
            else:
                if not o_queue_exceeds_safe_threshold(): # Skipping when it's 90% full. The remaining 10% is given to detected frames
                    # store frame in output queue
                    o_queue.put((main_fps._numFrames, {"detected": 0, "frame": frame, "frame_timestamp": frame_timestamp}))
                    main_fps.update()
                else:

                    try:
                        if int((datetime.now() - printout_since).total_seconds()) > 30:
                            printout_since = datetime.now()
                            print("o_queue 90% full...")
                            print("...Can't add new frames to o_queue")
                    except:
                        printout_since = datetime.now()

                    
                    

            # -> if frame is not None and not np.array_equal(last_frame, frame):


        if first_frame_detected and not run_tracking_loop:
            run_tracking_loop = True

            # t = Thread(target=tracking_loop, args=())
            # t.daemon = True
            # t.start()
            #tracking_pool = Pool(1, tracking_loop)
            
            tl = multiprocessing.Process(target=tracking_loop)
            tl.start()



            
        count += 1


        feed_loop_end_time = time.time()
        #print("FEED LOOP TIME:", feed_loop_end_time-feed_loop_start_time)




except:
    import traceback
    traceback.print_exc()
    
finally:

    # print("FINISHING UP ITEMS IN p_queue")
    # p_queue.join() # Only works if tracking_loop runs under same process as this

    print("TERMINATING detection_loop")
    dl.terminate()
    print("TERMINATING tracking_loop")
    tl.terminate()
    print("TERMINATING tracklets_loop")
    tsl.terminate()

    
    #print("CLOSING POOL")
    #pool.close()
    #tracking_pool.close()
    #print("TERMINATING POOL")
    #pool.terminate()
    #tracking_pool.terminate()

    #pool.join()
    #tracking_pool.join()

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
    
    print("[INFO] elasped time: {:.2f}".format(main_fps.elapsed()))
    print("[INFO] approx. Main FPS: {:.2f}".format(main_fps.fps()))
    #print("[INFO] approx. Tracking_Loop FPS: {:.2f}".format(tracking_loop_fps.fps()))
