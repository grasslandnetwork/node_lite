import numpy as np
import cv2
import os
import json
import requests
import plyvel
import multiprocessing
from multiprocessing import Queue, Pool
import gevent
from gevent.server import StreamServer
import time
from pathlib import Path

class MyException(Exception):
    pass

class RealWorldCoordinates:
    def __init__(self, tracking_frame):
        
        # Create node's personal leveldb database if missing
        self.node_db = plyvel.DB(str(Path.home())+'/.grassland/node_db/', create_if_missing=True)
        self.CALIBRATING = False
        self.tracking_frame = tracking_frame
        self.calibration = {}

        # pts_src and pts_dst are numpy arrays of points
        # in source and destination images. We need at least 
        # 4 corresponding points. 
        pts_src = np.array([[421, 695], [1587, 198], [368, 309], [1091, 98]])
        pts_dst =  np.array([[581, 473], [618, 215], [296, 449], [281, 245]])
        h, status = cv2.findHomography(pts_src, pts_dst)



    def set_transform(self, calibrating=False):
        self.CALIBRATING = calibrating

        # Get the real world transform that gets the longitude and latitude coordinates of each pixel of the realigned image
        # Using the node calibration web app, we can make a function that will allow the node to know what the real world (lat/lng) coordinates are for each pixels in it's frame
        # The node calibration web app using Mapbox and Open Street Map can map its pixels coordinates (2D space 'F') to a latitude and longitude coordinate (2D space 'W').
        # By lining up the Open Street Map "camera"" to exactly match the perspective of the real camera in the node, we can take a few pixels coordinates from 'F'
        # and their coresponding real world coordinates 'W' from the web app and use that to find a function, a linear map (transformation matrix), 'L'
        # that will take any pixel coordinate from the space 'F' and produce the cooresponding coordinate in 'W'. L(f) = w

        # 
        # Code taken From https://stackoverflow.com/a/20555267/8941739


        #primary = np.array([[0.0, 0.0], [1366.0, 0.0], [1366.0, 662.0], [0.0, 662.0]]) # Average dimensions of monitor viewing webapp. Maybe I should change this to be dynamic
        
        height = float(self.tracking_frame['height'])
        height = height / 2 # The modification made to mapbox (https://github.com/mapbox/mapbox-gl-js/issues/3731#issuecomment-368641789) that allows a greater than 60 degree pitch has a bug with unprojecting points closer to the horizon. They get very "screwy". So the two top homography_point corners in the web app ('ul' and 'ur') actually start half way down the canvas as the starting point to start from below the horizon
                                            
        width = float(self.tracking_frame['width'])
        primary = np.array([[0.0, 0.0], [width, 0.0], [width, height], [0.0, height]]) 
        
        
        # if not dynamic: # 
        #     secondary = np.array([[-75.75021684378025, 45.393495598366655], [-75.7512298958311, 45.39309963711102], [-75.75150315621723, 45.393444401619234], [-75.75049010416637, 45.393840360459365]])

        secondary_array = []


        '''
        Sample Node Format
        {
            'id': 'n68b5a19ef9364a74ae73b069934b21a4',
            'tracking_frame': {'height': 281, 'width': 500},
            'calibration': {
                'lng_focus': -75.75107566872947,
                'bearing': 62.60000000000002,
                'lat_focus': 45.39331613895314,
                'pitch': 55.00000000000001,
                'homography_points': {
                    'corners': {
                        'ul': {
                            'lat': 45.395059987864016,
                            'lng': -75.75055046479982
                        },
                        'll': {
                            'lat': 45.392791493630654,
                            'lng': -75.75123398120483
                        },
                        'ur': {
                            'lat': 45.392869098373296,
                            'lng': -75.74893325620522
                        },
                        'lr': {
                            'lat': 45.39362547029299,
                            'lng': -75.75184957418519
                        }
                    },
                    'markers': {}
                }
            }
        }


        '''
        # MySQL

        if self.CALIBRATING:
            # Get calibration values from Calibration Map
            # https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_event_loop
            # asyncio.get_event_loop().run_until_complete(self.call_websocket())
            #self.msl = multiprocessing.Process(target=self.mapserver_loop)
            #self.msl.daemon = True
            #self.msl.start()
            #print("Finished starting msl")
            self.calibration_socket_server = StreamServer(('127.0.0.1', 8765), self.calibration_socket_server_handler)
            self.calibration_socket_server.start()

            
        self.node_get()
        
        corner_names = ['ul', 'ur', 'll', 'lr']
        for corner_name in corner_names:
            ul_lng = self.calibration['homography_points']['corners'][corner_name]['lng']
            ul_lat = self.calibration['homography_points']['corners'][corner_name]['lat']
            secondary_array.append([ul_lng, ul_lat])


        secondary = np.array(secondary_array)
            

        # Pad the data with ones, so that our transformation can do translations too
        n = primary.shape[0]
        pad = lambda x: np.hstack([x, np.ones((x.shape[0], 1))])
        unpad = lambda x: x[:,:-1]
        X = pad(primary)
        Y = pad(secondary)

        # Solve the least squares problem X * A = Y
        # to find our transformation matrix A
        A, res, rank, s = np.linalg.lstsq(X, Y)

        # Real World Transform
        self.rw_transform = lambda x: unpad(np.dot(pad(x), A))

        np.set_printoptions(suppress=True)


        print("Target:")
        print(secondary)
        print("Result:")
        print(self.rw_transform(primary))
        print("Max error:", np.abs(secondary - self.rw_transform(primary)).max())
        A[np.abs(A) < 1e-10] = 0  # set really small values to zero
        print(A)
        print("Now Try it")
        print(self.rw_transform(np.array([[300, 200]])))
        print(self.rw_transform(np.array([[300.0, 200.0]])))


        
    def node_update(self):
        
        self.node_get()
        
        #node_id = os.environ['NODE_ID']
        #gl_api_endpoint = os.environ['GRASSLAND_API_ENDPOINT']
        # data = { "id": node_id, "tracking_frame": self.tracking_frame, "calibration": self.calibration }
        #response = requests.put(gl_api_endpoint+"node_update", json=data)

        tracking_frame_string = json.dumps(self.tracking_frame)
        self.node_db.put(b'tracking_frame', bytes(tracking_frame_string, 'utf-8'))

        calibration_string = json.dumps(self.calibration)
        self.node_db.put(b'calibration', bytes(calibration_string, 'utf-8'))


        
    def node_get(self):

        if self.CALIBRATING:
            self.call_gevent_wait()
            
            
        #node_id = os.environ['NODE_ID']
        # gl_api_endpoint = os.environ['GRASSLAND_API_ENDPOINT']
        # response = requests.get(gl_api_endpoint+"node_get"+"?id="+str(node_id))


        # tracking_frame = self.node_db.get(b'tracking_frame')
        # if tracking_frame == None: # THROW ERROR
        #     raise MyException("!!! leveldb get 'tracking_frame' returned None !!!!")
        # else:
        #     print(tracking_frame)
        #     self.tracking_frame = json.loads(tracking_frame.decode("utf-8"))


        if self.CALIBRATING:
            calibration = self.node_db.get(b'calibration')
            
            if calibration == None:
                self.call_gevent_wait() 
                timeout = time.time() + 60*5   # 5 minutes from now
                print("WAITING FOR YOU TO USE THE MAPSERVER TO SET THE CALIBRATION VALUES IN THE DATABASE ...")
                while True:
                    if time.time() > timeout:
                        print("TIMED OUT WAITING FOR THE CALIBRATION TO BE SENT FROM THE MAP SERVER!!")
                        break
                    
                    calibration = self.node_db.get(b'calibration')

                    if calibration == None:
                        self.call_gevent_wait() 
                    else:
                        self.calibration = json.loads(calibration.decode("utf-8"))
                        break
                        
            else:
                print(calibration.decode("utf-8"))
                self.calibration = json.loads(calibration.decode("utf-8"))

        else:
            calibration = self.node_db.get(b'calibration')
            if calibration == None: # THROW ERROR
                raise MyException("!!! leveldb get 'calibration' returned None. Restart with '--mode CALIBRATING' !!!!")
            else:
                print(calibration)
                self.calibration = json.loads(calibration.decode("utf-8"))

        

        
    def coord(self, x, y):

        coord = self.rw_transform(np.array([[x, y]]))

        return {
            "lng": coord[0][0],
            "lat": coord[0][1]
        }


        
    def calibration_socket_server_handler(self, socket, address):

        calibration_bytes_object = socket.recv(4096)
        # print("calibration_bytes_object")
        # print(calibration_bytes_object)


        # Store calibration in leveldb
        #self.node_db.put(b'calibration', bytes(calibration_string, 'utf-8'))
        self.node_db.put(b'calibration', calibration_bytes_object)

        # Get it back
        calibration = self.node_db.get(b'calibration')

        self.calibration = json.loads(calibration.decode("utf-8"))


        # Get camera frame dimensions (frame_dim). Could pull from database but this is easier
        tracking_frame_string = json.dumps(self.tracking_frame)
        # Send camera frame dimensions (frame_dim)
        socket.sendall(bytes(tracking_frame_string, 'utf-8'))
        

    def call_gevent_wait(self):
        gevent.wait(timeout=1) # https://stackoverflow.com/a/10292950/8941739
