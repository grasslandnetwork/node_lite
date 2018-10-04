class TrackableObject:
    def __init__(self, objectID, centroid, boxoid):
        # store the object ID, then initialize a list of centroids
        # using the current centroid
        self.objectID = objectID
        self.centroids = [centroid]
        self.boxoids = [boxoid]

        # initialize a boolean used to indicate if the object has
        # already been counted or not
        self.counted = False
