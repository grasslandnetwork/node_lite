import numpy as np
import cv2



# TL is the SE corner
# 0, 0  = [-75.75021684378025, 45.393495598366655]
	
# TR is SW Corner
# 1366, 0 = [-75.7512298958311, 45.39309963711102]

# BR is NW corner
# 1366, 662 = [-75.75150315621723, 45.393444401619234]

# BL is NE corner
# 0, 662 = [-75.75049010416637, 45.393840360459365]




class RealWorldCoordinates:
    def __init__(self):
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



    def set_transform(self, dynamic=False, gl_nodes=None):

        # Get the real world transform that gets the longitude and latitude coordinates of each pixel of the realigned image
        # From https://stackoverflow.com/a/20555267/8941739
        primary = np.array([[0.0, 0.0], [1366.0, 0.0], [1366.0, 662.0], [0.0, 662.0]])
        if not dynamic:
            secondary = np.array([[-75.75021684378025, 45.393495598366655], [-75.7512298958311, 45.39309963711102], [-75.75150315621723, 45.393444401619234], [-75.75049010416637, 45.393840360459365]])
        else:
            secondary_array = []
            corner_names = [u'ul', u'ur', u'll', u'lr']
            for corner_name in corner_names:
                ul_lng = gl_nodes.document('0').get().to_dict()[u'homography_points'][u'corners'][corner_name][u'lng']
                ul_lat = gl_nodes.document('0').get().to_dict()[u'homography_points'][u'corners'][corner_name][u'lat']

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


    def coord(self, x, y):

        coord = self.rw_transform(np.array([[x, y]]))

        return [coord[0][0], coord[0][1]]


           
