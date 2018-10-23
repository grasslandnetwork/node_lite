import numpy as np
import cv2
import os
import json

# TL is the SE corner
# 0, 0  = [-75.75021684378025, 45.393495598366655]
	
# TR is SW Corner
# 1366, 0 = [-75.7512298958311, 45.39309963711102]

# BR is NW corner
# 1366, 662 = [-75.75150315621723, 45.393444401619234]

# BL is NE corner
# 0, 662 = [-75.75049010416637, 45.393840360459365]


class MyException(Exception):
    pass

class RealWorldCoordinates:
    def __init__(self):
        self.calibration = {}
        # pts_src and pts_dst are numpy arrays of points
        # in source and destination images. We need at least 
        # 4 corresponding points. 
        pts_src = np.array([[421, 695], [1587, 198], [368, 309], [1091, 98]])
        pts_dst =  np.array([[581, 473], [618, 215], [296, 449], [281, 245]])
        h, status = cv2.findHomography(pts_src, pts_dst)


        # The calculated homography can be used to warp 
        # the source image to destination. Size is the 
        # size (width,height) of im_dst


        im_src = cv2.imread("10.jpg")
        dst_size = (1366, 662)
        src_size = (1920, 1080)

        
        self.im_dst = cv2.warpPerspective(im_src, h, dst_size)


    def show_image(self):
        

        # Show output
        cv2.imshow("Image", self.im_dst)
        cv2.waitKey(0)



    def set_transform(self):

        # Get the real world transform that gets the longitude and latitude coordinates of each pixel of the realigned image
        # From https://stackoverflow.com/a/20555267/8941739
        primary = np.array([[0.0, 0.0], [1366.0, 0.0], [1366.0, 662.0], [0.0, 662.0]])
        
        # if not dynamic: # 
        #     secondary = np.array([[-75.75021684378025, 45.393495598366655], [-75.7512298958311, 45.39309963711102], [-75.75150315621723, 45.393444401619234], [-75.75049010416637, 45.393840360459365]])

        secondary_array = []

        # Firebase's Firestore
        # corner_names = [u'ul', u'ur', u'll', u'lr']
        # for corner_name in corner_names:
        #     ul_lng = gl_nodes.document('0').get().to_dict()[u'homography_points'][u'corners'][corner_name][u'lng']
        #     ul_lat = gl_nodes.document('0').get().to_dict()[u'homography_points'][u'corners'][corner_name][u'lat']
        #     secondary_array.append([ul_lng, ul_lat])

        '''
        Sample Calibration Format
        {'lng_focus': -75.75107566872947, 'bearing': 62.60000000000002, 'tracking_frame': {'height': 281, 'width': 500}, 'lat_focus': 45.39331613895314, 'pitch': 55.00000000000001, 'homography_points': {'corners': {'ul': {'lat': 45.395059987864016, 'lng': -75.75055046479982}, 'll': {'lat': 45.392791493630654, 'lng': -75.75123398120483}, 'ur': {'lat': 45.392869098373296, 'lng': -75.74893325620522}, 'lr': {'lat': 45.39362547029299, 'lng': -75.75184957418519}}, 'markers': {}}}

        '''
        # MySQL
        corner_names = ['ul', 'ur', 'll', 'lr']
        self.calibration_get()
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


    # Used for Firebase's Firestore
    # def coord(self, x, y): 

    #     coord = self.rw_transform(np.array([[x, y]]))

          # Returns a list (array) because of Firebase's Firestore
    #     return [coord[0][0], coord[0][1]]


        
    def calibration_update(self):
        node_id = os.environ['NODE_ID']
        gl_api_endpoint = os.environ['GRASSLAND_API_ENDPOINT']
        data = { "node_id": node_id, "calibration": self.calibration }
        response = requests.post(gl_api_endpoint+"calibration_update", json=data)

        if response.status_code != 200:
            print(response.text)
            raise MyException("Grassland API Error Code: "+str(response.status_code))

        
    def calibration_get(self):
        node_id = os.environ['NODE_ID']
        gl_api_endpoint = os.environ['GRASSLAND_API_ENDPOINT']
        response = requests.get(gl_api_endpoint+"calibration_get"+"?node_id="+str(node_id))

        if response.status_code == 200:
            response_dict = json.loads(response.text)
            db_result_dict = response_dict['db_results']
            calibration = db_result_dict['calibration']
            self.calibration = calibration
        else:
            print(response.text)
            raise MyException("Grassland API Error Code: "+str(response.status_code))

        
    def coord(self, x, y):

        coord = self.rw_transform(np.array([[x, y]]))

        return {
            "lng": coord[0][0],
            "lat": coord[0][1]
        }


           
