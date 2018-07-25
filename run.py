#!/usr/bin/env python
import io
import socket
import struct
import time
import sys
import picamera
import pickle
import numpy as np
from PIL import Image
import cv2

import detection_visualization_util 



def load_image_into_numpy_array(image):
    (im_width, im_height) = image.size
    return np.array(image.getdata()).reshape((im_height, im_width, 3)).astype(np.uint8)


# Connect a client socket to detection server
# From https://stackoverflow.com/q/42458475
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host = '165.227.43.42' # needs to be in quote
port = 8000

client_socket.connect((host, port))
makefile_conn = client_socket.makefile('wb')

print("Socket Connected")


# Because client would sometimes hang indefinitely on 'recv' when receiving detections for second image ...
# ..and settimeout([float]) wouldn't work. And sometimes I'd get error 'EOFError: Ran out of input'
# From https://www.binarytides.com/receive-full-data-with-the-recv-socket-function-in-python/
def recv_timeout(the_socket,timeout=2): 
    #make socket non blocking
    the_socket.setblocking(0)
     
    #total data piecewise
    total_data = b''
     
    #beginning time
    begin=time.time()
    while True:
        #if you got some data, then break after timeout
        if total_data and time.time()-begin > timeout:
            break
         
        #if you got no data at all, wait a little longer, twice the timeout
        elif time.time()-begin > timeout*2:
            break
         
        #recv something
        try:
            data = the_socket.recv(1)
            if data:
                total_data += data
                #change the beginning time for measurement
                begin = time.time()
            else:
                #sleep for sometime to indicate a gap
                time.sleep(0.1)
        except:
            pass

    the_socket.setblocking(1)
    
    return total_data



def recv_augmented(the_socket, NAME):

    try:
        # RECEIVE BYTE_SIZE_OF_[NAME]
        data = the_socket.recv(4096).decode()
        if data.startswith("BYTE_SIZE_OF_"+NAME):
            # TELL SERVER WE'VE RECEIVED BYTE_SIZE_OF_[NAME]
            message_received = "RECEIVED BYTE_SIZE_OF_"+NAME
            print(message_received)
            client_socket.sendall(message_received.encode())

            tmp = data.split()
            byte_size_of_NAME = int(tmp[1])

            # RECEIVE [NAME]
            #data = client_socket.recv(byte_size_of_NAME) #Don't use anymore since it causes 'EOFError: Ran out of input'
            data = recv_timeout(client_socket)

            NAME_data = pickle.loads(data)

            if type(NAME_data) == np.ndarray:

                # TELL SERVER WE'VE RECEIVED [NAME]
                data_received = "RECEIVED "+NAME
                client_socket.sendall(data_received.encode())
                print(data_received)
                print(NAME_data)

                return True, NAME_data
            else:
                return False, None
            
    except:
        import traceback
        traceback.print_exc()

        return False, None




try:

    camera = picamera.PiCamera()
    camera.resolution = (640, 480)
    #camera.resolution = (1920, 1080)
    # Start a preview and let the camera warm up for 2 seconds
    print("[INFO] Warming up camera...")
    #camera.start_preview()
    time.sleep(2)

    # Construct a stream to hold image data
    start = time.time() # Note the start time
    stream = io.BytesIO()
    for foo in camera.capture_continuous(stream, 'jpeg'):
        print(" ")
        print(" ")
        print("..................")
        print("Starting new image")
        
        
        # send image size to server
        size = stream.tell()
        
        sending_size = "SIZE %s" % size
        client_socket.sendall(sending_size.encode())

        # answer should be 'RECEIVED SIZE'
        answer = client_socket.recv(4096).decode()
    
        print('SERVER %s' % answer)

        # send image to server
        if answer == 'RECEIVED SIZE':

            # Rewind the stream and send the image data over the wire
            stream.seek(0)

            
            makefile_conn.write(stream.read())
            # Flush to ensure it actually gets sent
            makefile_conn.flush()
            
            # check what server sends back
            answer = client_socket.recv(4096).decode()
            
            print('SERVER %s' % answer) # Should be 'RECEIVED IMAGE'
                
            if answer == 'RECEIVED IMAGE':
                print('Image successfully sent to server')

                # GET PROCESSED IMAGE DATA

                client_socket.sendall("SEND NUM_DETECTIONS".encode())


                # RECEIVE NUM DETECTIONS
                data = client_socket.recv(4096).decode()
                if data.startswith("NUM_DETECTIONS"):
                    # TELL SERVER WE'VE RECEIVED NUM_DETECTIONS
                    client_socket.sendall("RECEIVED NUM_DETECTIONS".encode())
                    print('RECEIVED NUM_DETECTIONS')

                    tmp = data.split()
                    num_detections_data = int(tmp[1])
                    print(num_detections_data)

                    if num_detections_data >= 1: # No point in continuing if there's 0 detections

                        go_ahead, detection_boxes_data = recv_augmented(client_socket, "DETECTION_BOXES")  

                        if go_ahead:
                            go_ahead, detection_scores_data = recv_augmented(client_socket, "DETECTION_SCORES")  

                            if go_ahead:
                                go_ahead, detection_classes_data = recv_augmented(client_socket, "DETECTION_CLASSES")  


                                ### >>>
                                # ( This code block will be removed eventually )
                                # Only use if programmer wants to visually verify detection server's bounding boxes. VERY, VERY, VERY SLOW ...
                                # ... Instead use detection_visualization_util to add bounding boxes to image locally
                                #if go_ahead:
                                    #client_socket.sendall("SEND IMAGE_WITH_BOUNDING_BOXES")
                                    #go_ahead, image_with_bounding_boxes_data = recv_augmented(client_socket, "IMAGE_WITH_BOUNDING_BOXES")  

                                    #print("SHOWING IMAGE WITH BOUNDING BOXES")
                                    #image_np = image_with_bounding_boxes_data
                                    #cv2.imshow("image", image_np);
                                    #cv2.waitKey(1)
                                ### <<<

                                    
                                output_dict = dict()
                                output_dict['num_detections'] = num_detections_data
                                output_dict['detection_boxes'] = detection_boxes_data
                                output_dict['detection_scores'] = detection_scores_data
                                output_dict['detection_classes'] = detection_classes_data

                                
                                # Code to add box for tracking will go here

                                


                # If we've been capturing for more than 600 seconds, quit
                # if time.time() - start > 60:
                #     print("60 seconds over. Quitting")
                #     break

                
                # Reset the stream for the next capture
                stream.seek(0)
                stream.truncate()


except:
    import traceback
    traceback.print_exc()
        
finally:

    print("Disconnecting")

    #send RECONNECT message to close and reconnect connection and makefile
    client_socket.sendall("RECONNECT ".encode())

    try:
        camera.close()
    except:
        pass
        
    try:
        makefile_conn.close()
    except:
        pass
    
    client_socket.close()
    sys.exit("Exiting")
    
    






















