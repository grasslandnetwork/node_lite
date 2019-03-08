class TrackableObject:
    def __init__(self, objectID, centroid_frame_timestamp, detection_class_id, centroid, boxoid, bbox_rw_coords):
        # store the object ID, then initialize a list of centroids
        # using the current centroid
        self.objectID = objectID

        # initialize instance variable, 'oids' as a list
        self.oids = []
        
        # initialize instance variable, 'centroids' as a list
        self.centroids = []

        # initialize instance variable, 'boxoids' as a list
        self.boxoids = []

        # initialize instance variable, 'bbox_rw_coords' as a list
        self.bbox_rw_coords = []

        # initialize instance variable 'detection_class_id' as 0
        self.detection_class_id = detection_class_id

        # initialize a boolean used to indicate if the object has
        # already been counted or not
        self.counted = False

        # initialize a boolean used to indicate if the object has left the node's field of view and the tracks complete
        self.complete = False

        # pass first boxoid to 'append_boxoids' method for processing
        self.append_boxoid(boxoid)

        # pass first centroid to 'append_centroids' method for processing
        self.append_centroid(centroid)


        self.append_oids(centroid_frame_timestamp, detection_class_id, centroid, boxoid, bbox_rw_coords)



    def append_centroid(self, centroid):
        pass
        #self.centroids.append(list(centroid))
        
        
    def append_boxoid(self, boxoid):

        #self.boxoids.append(list(boxoid))

        # if self.detection_class_id > 0 and boxoid[5] <= 0: # if object's class has been identified already but this isn't a new identification
        #     pass # ... then don't change the current detection class. Even if the new detection_class_id is a -1, which means that the detection has changed but we'll stick with the first detected object class
        # else: # if the object's class hasn't been identified yet or this is a new identification from a detected frame or a -1
        #     self.detection_class_id = boxoid[5]

        pass
    

    def append_oids(self, centroid_frame_timestamp, detection_class_id, centroid, boxoid, bbox_rw_coords):

        if self.detection_class_id > 0 and detection_class_id <= 0: # if object's class has been identified already but this isn't a new identification
            pass # ... then don't change the current detection class. Even if the new detection_class_id is a -1, which means that the detection has changed but we'll stick with the first detected object class
        else: # if the object's class hasn't been identified yet or this is a new identification from a detected frame or a -1
            self.detection_class_id = detection_class_id


        oid = {
            "frame_timestamp": centroid_frame_timestamp,
            "centroid": list(centroid),
            "boxoid": list(boxoid),
            "bbox_rw_coords": bbox_rw_coords
        }
        
        self.oids.append(oid)
