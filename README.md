# Grassland Node_Lite

### A Grassland mining node that can run on mini computers like the Raspberry Pi 3 or older desktops and laptops. This repo is the client side to the Serverless [Node Lite Object Detection](https://github.com/grasslandnetwork/node_lite_object_detection) AWS Lambda function which handles the node's object detections. 

### Installation
#### Requires at least 4 GB's of RAM and Python 3.6 or greater. It's recommended that you use a Python virtual environment

Clone this repo on your own machine. 'cd' to the project's root directory and install the required modules using

```pip install -r requirements.txt```

### Running Your Node
You'll need to calibrate your node the first time you run it. So we'll also need to load the node's GUI (graphical user interface) which helps you visually calibrate the orientation of the node's camera in the real world.

Before we start the node, open a second bash terminal and cd to the projects 'gui' subfolder. 
```cd gui```

Then return to the first terminal and type

```python multi_object_tracking.py [ --options <arg> ]...```

--Options <Arguments> Description
  --mode <ONLINE> | <CALIBRATING> [default: ONLINE] "If ONLINE, data is stored in main database. CALIBRATING is used for setting camera orientation in the map"
  
  --display <0> | <1> [default: 0] "Displays the input video feed in console with tracked objects and bounding boxes. Useful for debugging the tracker and object detector. If not needed, do not use as it consumes uncessary computation."
  
  --picamera <0> | <1> [default: 0] "By default, the computer's webcamera is used as input. If running on a Raspberry Pi, set this option to use the Pi's attached camera as input"
  
  --rotation (<0> | <90> | <180> | <270>) [default: 0] "If a Raspberry Pi camera is used for input instead of the webcamera (default), this specifies camera's clockwise rotation"
  
  --video <path/to/video/file> "For debugging purposes, a video file can be used as input instead of an attached webcamera (default). This specifies path to video file
  
  --num_workers <#> [default: 5] "For computers with multi-core CPU's, spreads tasks into separate processes to parralelize processes and speed up software"

The software should start running and pause as it's waiting for you to set the calibration. Go to the second terminal in project's 'gui' directory and type

```npm run dev```

After compilation, this will open up your browser to the map. 




#### Unless otherwise specified, this software is released under the terms of the Grassland License. It's identical to the Mozilla Public License 2.0 with the added restriction that the use of this Work or its Derivatives to gather data that comes from locations in which an uninformed third party would have no reasonable expectation of privacy is governed by our open data policy wherein all data gathered from such locations shall be made freely available to anyone with the same frequency, format and specifications to that of approved Grassland Node implementations. Approved Grassland Node implementations can be found on our Github page located here -> [https://github.com/grasslandnetwork/](https://github.com/grasslandnetwork/)
