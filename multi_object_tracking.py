# import the necessary packages
from imutils.video import VideoStream
from imutils.video import FileVideoStream
from imutils.video import FPS
import argparse
import imutils
import time
import cv2
from lnglat_homography import RealWorldCoordinates
from datetime import datetime, timezone
import os
import numpy as np
import multiprocessing
from multiprocessing import Queue, Pool
from queue import PriorityQueue
from queue import Empty
import requests
import boto3
from PIL import Image
import json
import sys
from threading import Thread
import detection_visualization_util
from random import randint
import concurrent.futures
from pyimagesearch.centroidtracker import CentroidTracker
from pyimagesearch.trackableobject import TrackableObject

import plyvel
import s2sphere


import gevent
from gevent.server import StreamServer
from gevent.queue import Queue as GeventQueue

from multiprocessing import Value

node_id = os.environ['NODE_ID']
frame_s3_bucket_name = os.environ['GRASSLAND_FRAME_S3_BUCKET']

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("--mode", type=str, default='ONLINE',
                help="'ONLINE' or 'CALIBRATING' [default: ONLINE]")
ap.add_argument("--display", type=int, default=0,
                help="Displays the input video feed in console with tracked objects and bounding boxes. Useful for debugging the tracker and object detector. If not needed, do not use as it consumes uncessary computation. [default: 0]")
ap.add_argument("--picamera", type=int, default=0,
                help="DEPRECATED: By default, the computer's webcamera is used as input. If running on a Raspberry Pi, set this option to use the Pi's attached camera as input. [default: 0]")
ap.add_argument("--rotation", type=int, default=0,
                help="DEPRECATED: If a Raspberry Pi camera is used for input instead of the webcamera (default), this specifies camera's clockwise rotation. Valid values are 0, 90, 180, and 270. [default: 0]")
ap.add_argument("--video", type=str,
                help="For debugging purposes, a video file can be used as input. This specifies path to video file.")
ap.add_argument("--num_workers", type=int, default=5,
                help="For computers with multi-core CPU's, spreads tasks into separate processes to parralelize processes and speed up software [default: 5]")
ap.add_argument("--tracker", type=str, default="mosse",
                help="OpenCV object tracker type, [default: mosse]")
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

run_tracklets_socket_server = Value('i', 1)


s3_res = boto3.resource('s3')
s3_bucket = s3_res.Bucket(frame_s3_bucket_name)

lambda_url = os.environ['LAMBDA_DETECTION_URL']

tracklets_queue_max = 100
o_queue_max = 80
p_queue_max = 300

tracklets_queue = Queue() # tracklets queue
mapserver_tracklets_queue = GeventQueue() # calibration tracklets queue    
i_queue = Queue() # input queue    
o_queue = Queue(maxsize=o_queue_max) # output queue
p_queue = PriorityQueue(maxsize=p_queue_max) # priority queue


#### !!! WARNING !!! --> Store s2sphere in bigendian format to order bytes lexicographically in LevelDB
s2sphere_byteorder = 'big'

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
        response = requests.get(lambda_url+"?bucket="+frame_s3_bucket_name+"&key="+file_name_ext)

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
        


print("NODE IS IN '", args['mode'], "' MODE")
# if a video path was not supplied, grab the reference to the web cam
if not args.get("video", False):
    framerate = 30
        
    print("[INFO] starting camera stream...")    
    vs = VideoStream(usePiCamera=args["picamera"], resolution=(detection_frame_width, int(detection_frame_width*frame_ratio)), framerate=framerate).start()
    print("[INFO] Warming up camera...")
    time.sleep(3)
    
    if args["picamera"] == 1 or args["picamera"] == True:
        vs.camera.rotation = args["rotation"]
    
    
else: # otherwise, grab a reference to the video file
    framerate = 30
    print("[INFO] starting video file stream...")    
    vs = FileVideoStream(args["video"], queueSize=15).start()

    # loop over frames from the video stream




    
'''
Here we calculate and set the linear map (transformation matrix) that we use to turn the pixel coordinates of the objects on the frame into their corresponding lat/lng coordinates in the real world. It's a computationally expensive calculation and requires inputs from the camera's calibration (frame of reference in the real world) so we do it once here instead of everytime we need to do a transformation from pixels to lat/lng
'''
rw = RealWorldCoordinates({"height": tracking_frame_width*frame_ratio, "width": tracking_frame_width})
if args['mode'] == 'CALIBRATING':
    rw.set_transform(calibrating=True)
    print("set calibration")
else:
    rw.node_update()
    rw.set_transform() 


# Set Leveldb database variable
if args['mode'] == 'CALIBRATING':
    tracklets_db = plyvel.DB('/tmp/gl_tmp_tracklets_db/', create_if_missing=True)
else:
    tracklets_db = plyvel.DB('/tmp/gl_tracklets_db/', create_if_missing=True)

# Use current eon number for LevelDB prefix to partition database
# https://plyvel.readthedocs.io/en/latest/user.html#prefixed-databases
eon_tracklets_db = tracklets_db.prefixed_db(b'\x00') 


        
first_frame_detected = False
if args["display"] == 1:
    display = True
else:
    display = False
    
run_tracking_loop = Value('i', 0)
run_detection_loop = Value('i', 0)

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

def post_tracklet(tracklets_dict):
    post_tracklet_start_time = time.time()

    print("Making request on lambda")
    if args['mode'] == 'ONLINE':
        tracklets_dict['node_mode'] = 'ONLINE'
        response = requests.post(gl_api_endpoint+"tracklets_create", json=tracklets_dict)
    elif args['mode'] == 'CALIBRATING':
        tracklets_dict['node_mode'] = 'CALIBRATING'
        response = requests.post(gl_api_endpoint+"tracklets_create", json=tracklets_dict)


    end_time = time.time()

    print("TRACKLET ROUND TRIP TIME:", end_time-post_tracklet_start_time)

    if args['mode'] == 'CALIBRATING': # To compare to when frames show up on server
        try:
            print("TRACKLET 'frame_timestamp'", tracklets_dict['tracklets'][0]['frame_timestamp'])
        except:
            pass




# this handler will be run for each incoming connection in a dedicated greenlet
def tracklets_socket_server_handler(socket, address):
    # print('New connection for tracklets from %s:%s' % address)

    # Read socket query
    query_dict =  json.loads(socket.recv(4096).decode('utf-8'))
    query_timestamp = query_dict['timestamp']
    query_range = query_dict['range']
    query_timestamp = int(query_timestamp)
    query_range = int(query_range)


    trackableObjects = {}
    for key, val in eon_tracklets_db:
        if query_timestamp <= int.from_bytes(key[8:], byteorder=s2sphere_byteorder) < query_timestamp+query_range:
            # print("query_timestamp")
            # print(query_timestamp)
            # print('int.from_bytes(key[8:], byteorder=s2sphere_byteorder)')
            # print(int.from_bytes(key[8:], byteorder=s2sphere_byteorder))
            # print("------------------------------------------")
            
            cell_id = int.from_bytes(key[0:8], byteorder=s2sphere_byteorder)
            s2_cellid = s2sphere.CellId(id_=cell_id)
            s2_latlng = s2_cellid.to_lat_lng()
            lat = s2_latlng.lat().degrees
            lng = s2_latlng.lng().degrees
            frame_timestamp = int.from_bytes(key[8:], byteorder=s2sphere_byteorder)

            if val[0:16].hex() in trackableObjects:
                
                trackableObjects[val[0:16].hex()]['tracklets'].append(
                    [
                        lng,
                        lat,
                        frame_timestamp 
                    ]
                )
            else:
                trackableObjects[val[0:16].hex()] = {
                    "detection_class_id": int.from_bytes(val[16:], byteorder=s2sphere_byteorder),
                    "tracklets": [
                        [
                            lng,
                            lat,
                            frame_timestamp
                        ]
                    ]
                }

    
    trackable_object_list = []
    for object_id, trackableObject in trackableObjects.items():

        trackable_object_list.append(

            {
                "object_id": object_id,
                "detection_class_id": trackableObject['detection_class_id'],
                "vendor": trackableObject['detection_class_id'],
                "tracklets": trackableObject['tracklets']
            }
        )
    

    if len(trackable_object_list) > 0:
        socket.sendall(bytes(str(trackable_object_list), 'utf-8'))
        print("sent "+str(len(trackable_object_list))+ " trackable objects for query_timestamp "+str(query_timestamp))
        #print(str(trackable_object_list))
    else:
        socket.sendall(bytes(str([]), 'utf-8')) # send an empty list
        

#### !!! WARNING !!! --> If writing to LevelDB in this loop, only run this in one process and avoid threads unless you use locking
# ... https://github.com/google/leveldb/blob/master/doc/index.md#concurrency
#### !!! WARNING !!! --> Store s2sphere in bigendian format to order bytes lexicographically in LevelDB
def tracklets_loop():
    try:


        # print("Start gevent server socket for mapserver to get tracklets")
        tracklets_socket_server = StreamServer(('127.0.0.1', 8766), tracklets_socket_server_handler)
        tracklets_socket_server.start()


        print("STARTING TRACKLETS_LOOP")

        while True:

            try:
                
                if run_tracklets_socket_server.value == 0:
                    tracklets_socket_server.stop(timeout=3)

                    break


                gevent.wait(timeout=1) # https://stackoverflow.com/a/10292950/8941739
                
                if not tracklets_queue.empty():

                    trackable_object = tracklets_queue.get(block=False)

                    with eon_tracklets_db.write_batch() as eon_tracklets_wb:
                        
                        for oid in trackable_object.oids:
                            bbox_rw_coords = oid['bbox_rw_coords']

                            lat = oid['bbox_rw_coords']['btm_center']['lat']
                            lng = oid['bbox_rw_coords']['btm_center']['lng']

                            '''
                            #### DISCREPANCY: S2sphere Cells VS. Lat, Lng
                            Since we're storing values in the database as s2sphere cells and not lat, lng coordinates the best precision we can get amounts to dividing up the earth into square centimeters, it's highest cell level. And if you ask for the lat, lng coordinate of that cell, it'll return the lat, lng coordinate at the centre of that cell. But the precision of the lat, lng coordinates from the map server is higher so the function "s2sphere.LatLng.from_degrees" will take any lat, lng coordinate you give it and return the cell in which it resides whose centre will always be half a centimetre or less away from it. So there will always be a discrepancy between the lat, lng coordinates coming from the map server/homography function and the lat, lng coordinate associated with the centre of the cell that is actually entered into the database. The lat, lng discrepancy can range from 1.0e-8 to 1.0e-10 degrees. 
                            '''

                            s2_latlng = s2sphere.LatLng.from_degrees(lat, lng)
                            s2_cellid = s2sphere.CellId.from_lat_lng(s2_latlng)

                            # Take the s2sphere cell ID (a 64-bit integer) and convert it to an 8 byte big-endian Python bytes object
                            cell_id_as_bytes = s2_cellid.id().to_bytes(8, byteorder=s2sphere_byteorder)
                            # Get the timestamp for when this tracklet occurred (But which end?)
                            frame_timestamp = oid['frame_timestamp'] # In milliseconds
                            # Convert frame_timestamp back to int since when it comes back from CentroidTracker it has a ".0" at the end
                            frame_timestamp = int(frame_timestamp)
                            # Convert that timestamp to bytes
                            frame_timestamp_as_bytes = frame_timestamp.to_bytes(6, byteorder=s2sphere_byteorder)
                            # Concatenate those bytes together. This is the LevelDB 'key' 
                            key = bytes(0).join( ( cell_id_as_bytes, frame_timestamp_as_bytes ) )

                            # The LevelDB 'value' is the concatenation of the objectID and its the detection_class_id 
                            # Convert objectID to bytes
                            objectID_as_bytes = bytes.fromhex(trackable_object.objectID) # 16 bytes
                            # Convert detection_class_id to bytes
                            detection_class_id_as_bytes  = (trackable_object.detection_class_id).to_bytes(2, byteorder=s2sphere_byteorder)
                            value = bytes(0).join( ( objectID_as_bytes, detection_class_id_as_bytes ) )

                            # Set the key value pair to be written to the database
                            eon_tracklets_wb.put(key, value)

                            # # print('Original Lat Lng')
                            # # print('OR lat ', lat)
                            # # print('OR lng ', lng)

                            # # print('S2 Lat Lng')
                            # s2_latlng_dup = s2_cellid.to_lat_lng()
                            # s2_lat = s2_latlng_dup.lat().degrees
                            # s2_lng = s2_latlng_dup.lng().degrees
                            # # print('s2 lat ', s2_lat)
                            # # print('s2 lng ', s2_lng)

                            # # print('DIFFERENCE lat ', lat - s2_latlng_dup.lat().degrees)
                            # # print('DIFFERENCE lng ', lng - s2_latlng_dup.lng().degrees)


                    if args['mode'] == 'CALIBRATING': # If we're in calibration mode show user the frame_timestamp
                        print("last frame_timestamp")
                        my_tz = datetime.now(timezone.utc).astimezone().tzinfo # Get local timezone
                        print( datetime.fromtimestamp(frame_timestamp/1000, my_tz).strftime("%B %d, %Y %I:%M %p") )



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
        
        if run_tracking_loop.value:
            print("STARTING TRACKING_LOOP")
        else:
            return
        
        #global tracking_loop_fps
        tracking_loop_fps = FPS().start()
        
        frame_loop_count = 0
        avg = None
        tracker_boxes = []
        track_centroids = True

        ct = CentroidTracker(maxDisappeared=10, maxDistance=tracking_frame_width/20)
        trackableObjects = {}
        
        
        while run_tracking_loop.value:
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
                run_tracking_loop.value = 0
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
                                # print("track_centroids frame_timestamp")
                                # print(frame_timestamp)
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

                        # # loop over the tracked objects to add them to objectsPositions and to trackableObjects
                        # objectsPositions = []
                        for (objectID, (centroid_frame_timestamp, centroid_detection_class_id, centroid, boxoid)) in objects.items():

                            if ct.disappeared[objectID] != 0:
                                continue
                                

                                
                            # # Calculate bottom center pixel coordinates
                            # #bottom_center_x = (boxoid[0] + boxoid[2]) / 2
                            # bottom_center_x = centroid[0]
                            # bottom_center_y = boxoid[3]


                            # objectsPositions.append({
                            #     "tracklet_id": objectID,
                            #     "node_id": node_id,
                            #     "bbox_rw_coord": {
                            #         "btm_left": rw.coord(boxoid[0], boxoid[3]),
                            #         "btm_right": rw.coord(boxoid[2], boxoid[3]),
                            #         "btm_center": rw.coord(bottom_center_x, bottom_center_y)
                            #     },
                            #     "frame_timestamp": boxoid[4],
                            #     "detection_class_id": boxoid[5]
                            # })

                            # Change centroid_detection_class_id from 1 x 1 numpy array to int
                            centroid_detection_class_id = int(centroid_detection_class_id[0])
                            
                            # Calculate bottom center pixel coordinates
                            #bottom_center_x = (boxoid[0] + boxoid[2]) / 2
                            bottom_center_x = centroid[0]
                            bottom_center_y = boxoid[3]

                            # Add bottom center pixel coordinates to trackable object
                            bbox_rw_coords = {
                                "btm_left": rw.coord(boxoid[0], boxoid[3]),
                                "btm_right": rw.coord(boxoid[2], boxoid[3]),
                                "btm_center": rw.coord(bottom_center_x, bottom_center_y)
                            }

                                
                            # check to see if a trackable object exists for the current
                            # object ID
                            to = trackableObjects.get(objectID, None)

                            # if there is no existing trackable object, create one
                            if to is None:
                                to = TrackableObject(objectID, centroid_frame_timestamp, centroid_detection_class_id, centroid, boxoid, bbox_rw_coords)

                            # otherwise, there is a trackable object so we can utilize it
                            # to determine direction
                            else:
                                # the difference between the y-coordinate of the *current*
                                # centroid and the mean of *previous* centroids will tell
                                # us in which direction the object is moving (negative for
                                # 'up' and positive for 'down')
                                # y = [c[1] for c in to.centroids]
                                # if len(y) > 0: # to avoid 'invalid value encountered in double_scalars' error (https://stackoverflow.com/a/33898520/8941739)
                                #     direction = centroid[1] - np.mean(y)
                                #to.append_centroid(centroid)
                                #to.append_boxoid(boxoid)
                                to.append_oids(centroid_frame_timestamp, centroid_detection_class_id, centroid, boxoid, bbox_rw_coords)




                            # store the trackable object in our dictionary
                            trackableObjects[objectID] = to

                            
                        ## Put tracklet tip data in queue via a separate process/thread
                        ## To update their position in database
                        # tracklets_queue.put({ "tracklets": objectsPositions })                                

                        

                        # For all the objects in trackableObjects

                        # After updating, if object has been marked as "deregistered" ...
                        # ... it's been completely tracked, add it to deregistered_objects list
                        deregistered_objects = []
                        for object_id, trackableObject in trackableObjects.items():
                            
                            if not ct.objects.get(object_id, False): 
                                deregistered_objects.append(object_id)

                        
                        # For each object in deregistered_objects
                        for object_id in deregistered_objects:
                            # ... mark the corresponding trackableObject's (in trackableObjects) 'complete' property as True
                            trackableObjects[object_id].complete = True

                            # If this trackable object has a detection, add this it to tracklets_queue for seralization/storage
                            if trackableObjects[object_id].detection_class_id > 0:
                                tracklets_queue.put(trackableObjects[object_id])                          

                            # Now remove this completed trackable object from the trackableObjects dictionary
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


                ## MOTION DETECTION. Accumulate the weighted average on every frame even if it's already detected
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

                

                if track_centroids and frame_dict.get("detected") == 0:
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
                    
                    if track_centroids and frame_dict.get("detected") == 0:
                        # add the bounding box coordinates to the rectangles list
                        # put 0 in detection_class_id section since we don't have a detection yet
                        rects.append((startX, startY, endX, endY, frame_timestamp, 0))

                if track_centroids and frame_dict.get("detected") == 0:
                    # use the centroid tracker to associate the (1) old object
                    # centroids with (2) the newly computed object centroids
                    objects = ct.update(rects)
                    
                    # # loop over the tracked objects to add them to objectsPositions and to trackableObjects
                    # objectsPositions = []

                    for (objectID, (centroid_frame_timestamp, centroid_detection_class_id, centroid, boxoid)) in objects.items():

                        if ct.disappeared[objectID] != 0:
                            continue

                        # # Calculate bottom center pixel coordinates
                        # #bottom_center_x = (boxoid[0] + boxoid[2]) / 2
                        # bottom_center_x = centroid[0]
                        # bottom_center_y = boxoid[3]


                        # objectsPositions.append({
                        #     "tracklet_id": objectID,
                        #     "node_id": node_id,
                        #     "bbox_rw_coord": {
                        #         "btm_left": rw.coord(boxoid[0], boxoid[3]),
                        #         "btm_right": rw.coord(boxoid[2], boxoid[3]),
                        #         "btm_center": rw.coord(bottom_center_x, bottom_center_y)
                        #     },
                        #     "frame_timestamp": boxoid[4],
                        #     "detection_class_id": boxoid[5]
                        # })

                        # Change centroid_detection_class_id from 1 x 1 numpy array to int
                        centroid_detection_class_id = int(centroid_detection_class_id[0])


                        # Calculate bottom center pixel coordinates
                        #bottom_center_x = (boxoid[0] + boxoid[2]) / 2
                        bottom_center_x = centroid[0]
                        bottom_center_y = boxoid[3]

                        # Add bottom center pixel coordinates to trackable object
                        #to.bbox_rw_coords.append(
                        bbox_rw_coords = {
                            "btm_left": rw.coord(boxoid[0], boxoid[3]),
                            "btm_right": rw.coord(boxoid[2], boxoid[3]),
                            "btm_center": rw.coord(bottom_center_x, bottom_center_y)
                        }

                        
                        # check to see if a trackable object exists for the current
                        # object ID
                        to = trackableObjects.get(objectID, None)

                        # if there is no existing trackable object, create one
                        if to is None:
                            to = TrackableObject(objectID, centroid_frame_timestamp, centroid_detection_class_id, centroid, boxoid, bbox_rw_coords)

                        # otherwise, there is a trackable object so we can utilize it
                        # to determine direction
                        else:
                            # the difference between the y-coordinate of the *current*
                            # centroid and the mean of *previous* centroids will tell
                            # us in which direction the object is moving (negative for
                            # 'up' and positive for 'down')
                            # y = [c[1] for c in to.centroids]

                            # if len(y) > 0: # to avoid 'invalid value encountered in double_scalars' error (https://stackoverflow.com/a/33898520/8941739)
                            #     direction = centroid[1] - np.mean(y)
                                
                            #to.append_centroid(centroid)
                            #to.append_boxoid(boxoid)
                            to.append_oids(centroid_frame_timestamp, centroid_detection_class_id, centroid, boxoid, bbox_rw_coords)

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

                        # print("trackableObjects key")
                        # trackable_objects_key = next(iter(trackableObjects))
                        # print(trackable_objects_key)
                        # print("trackable_object centroids")
                        # print(trackableObjects[trackable_objects_key].centroids)

                        # print("trackable_object boxoids")
                        # print(trackableObjects[trackable_objects_key].boxoids)

                        # print("trackable_object")
                        # obj = trackableObjects[trackable_objects_key]
                        # for attr in dir(obj):
                        #     print("obj.%s = %r" % (attr, getattr(obj, attr)))

                        
                        if display:
                            # draw both the ID of the object and the centroid of the
                            # object on the output frame
                            text = "ID {}".format(objectID[0:3])
                            cv2.putText(this_frame, text, (centroid[0] - 10, centroid[1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                            cv2.circle(this_frame, (centroid[0], centroid[1]), 4, (0, 255, 0), -1)


                    ## Put tracklet tip data in queue via a separate process/thread
                    ## To update their position in database
                    #tracklets_queue.put({ "tracklets": objectsPositions })                                

                    
                    # -> if track_centroids and frame_dict.get("detected") == 0:

                    
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

            
            # -> while run_tracking_loop.value:
                
            
    except:
        import traceback
        traceback.print_exc()

        raise


def detection_loop():
    try:

        if run_detection_loop.value:
            print("STARTING DETECTION_LOOP")
        else:
            return
            
        while run_detection_loop.value:

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
                        if int((datetime.now() - idle_since).total_seconds()) > 40: # If this loop has been idle
                            idle_since = datetime.now()
                            print("no i_queue items for detection loop .................")

                            if args['mode'] == 'CALIBRATING': # If we're in calibration mode and ...
                                if not run_tracking_loop.value: # ... the tracking loop's been stopped
                                    run_detection_loop.value = 0 # stop this loop

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


# if args['mode'] == 'CALIBRATING':
#     print("Start gevent server socket for mapserver to get tracklets")

#     tracklets_socket_server = StreamServer(('127.0.0.1', 8766), tracklets_socket_server_handler)
#     tracklets_socket_server.start()


run_detection_loop.value = 1            
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
                rw.tracking_frame = {"height": height, "width": width}
                rw.node_update()
                
                frame_dimensions_set = True

                
            if args['mode'] == 'CALIBRATING':
                try:
                    if int((datetime.now() - set_transform_since).total_seconds()) > 4: # Rebuild RW transformation matrix every 4 seconds
                        set_transform_since = datetime.now()
                        rw.set_transform(calibrating=True)
                except:
                    set_transform_since = datetime.now()


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


            else: # ... then don't perform detection on frame but just use for tracking (tracklet association) 
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


        if first_frame_detected and not run_tracking_loop.value:
            run_tracking_loop.value = 1

            # t = Thread(target=tracking_loop, args=())
            # t.daemon = True
            # t.start()
            #tracking_pool = Pool(1, tracking_loop)
            
            tl = multiprocessing.Process(target=tracking_loop)
            tl.start()



            
        count += 1


        feed_loop_end_time = time.time()
        #print("FEED LOOP TIME:", feed_loop_end_time-feed_loop_start_time)



    if args['mode'] == 'CALIBRATING':
        print("CALIBRATION mode keeps socket servers running waiting for KeyboardInterrupt from user...")
      
        while True:
            try:
                
                if dl.is_alive() and run_detection_loop.value == 0: 
                    print("TERMINATING detection_loop")
                    dl.terminate()
                    time.sleep(4)

                if tl.is_alive() and run_tracking_loop.value == 0:
                    print("TERMINATING tracking_loop")
                    tl.terminate()
                    time.sleep(4)
                    

            except:
                raise

        

        
except:
    import traceback
    traceback.print_exc()
    
finally:

    # print("FINISHING UP ITEMS IN p_queue")
    # p_queue.join() # Only works if tracking_loop runs under same process as this

    print("STOPPING SOCKET SERVER tracklets_socket_server")
    run_tracklets_socket_server.value = 0
    
    print("STOPPING SOCKET SERVER calibration_socket_server")
    rw.calibration_socket_server.stop(timeout=3)

    if dl.is_alive():
        print("TERMINATING detection_loop")
        dl.terminate()

    if tl.is_alive():
        print("TERMINATING tracking_loop")
        tl.terminate()

    if tsl.is_alive():
        print("TERMINATING tracklets_loop")
        tsl.terminate()


    print("CLOSE LEVELDB tracklets DATABASE")
    tracklets_db.close() # can't close prefixed database
    print("CLOSE LEVELDB node DATABASE")
    rw.node_db.close()  # can't close prefixed database


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








