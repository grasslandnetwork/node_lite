# Grassland Node_Lite

### A Grassland mining node that can run on mini computers or older desktops and laptops. This repo is the client side to the Serverless [Node Lite Object Detection](https://github.com/grasslandnetwork/node_lite_object_detection) AWS Lambda function which handles the node's object detections.


If you have questions related to this software, search in the 'Issues' tab of this Github repo to see if it's been answered. If not, feel free to open a new issue and I'll get back to you as soon as I can.


## Step 1: Installation
#### Developed and tested on Ubuntu 16.04 and Raspbian (a rebuild of Debian) 9 Stretch. Requires at least 4 GB's of RAM (Slower hardware like Rasberry Pi's can run software locally but aren't powerful enough for mining at mainnet speed requirements), Python 3.6 or greater and Node.js 8.10.0 or greater. It's recommended that you use a Python [virtual environment and virtual environment wrapper](https://docs.python-guide.org/dev/virtualenvs/) to create a separate virtual environment for your package dependencies


### Grassland Node Installation

Clone this repo on your own machine. 'cd' to the project's root directory and install the required Python packages using

```pip install -r requirements.txt```

#### AWS Credentials
This node version uses the [boto3](https://pypi.org/project/boto3/) (the Amazon Web Services (AWS) Software Development Kit) Python package to communicate with the Serverless [Node Lite Object Detection](https://github.com/grasslandnetwork/node_lite_object_detection) AWS Lambda instance to do the necessary object detections. If you haven't deployed that, please do so now by following the instructions in that repo.

You should have your AWS Access Key and AWS Secret Key as environment variables on your system by following the instructions on the Node Lite Object Detection [README](https://github.com/grasslandnetwork/node_lite_object_detection) 

```
export AWS_ACCESS_KEY_ID=<your-key-here>
export AWS_SECRET_ACCESS_KEY=<your-secret-key-here>
export LAMBDA_DETECTION_URL=<your-lambda-url-here>

# 'export' command is valid only for unix shells. In Windows - use 'set' instead of 'export'
```

You will now need to set the name of the S3 bucket you'll use to temporarily (they're deleted after detection) store the frames from your camera that will be used by the Lambda function for object detection as well as your AWS default region (e.g. ```us-east-1```) as environment variables

```
export AWS_DEFAULT_REGION=<your-default-region-here>
export GRASSLAND_FRAME_S3_BUCKET=<your-s3-bucket-name-here>
```


### Grassland GUI Installation

You'll need to calibrate your Grassland node the first time you run it by letting your node know where the camera its viewing is positioned in the real world. To do that easily we'll use the node GUI's (graphical user interface) simulated, 3D map of the world to virtually set a position and viewing angle that matches that of the camera in the real world. Your node will use this to automatically calculate the right calibration.


Before we start the node, open a second bash terminal and cd to the projects 'gui' subfolder.

```cd gui```

Then type

```npm install```

To use the map, you will need a free Mapbox Access Token. You can get a free Mapbox Access token here -> https://docs.mapbox.com/help/how-mapbox-works/access-tokens/

Make a note of your Mapbox token because we'll be using it later.


## Step 2: Run the Software
### Start The Grassland Node

Return to the first terminal to start the Grassland node. Type

```python multi_object_tracking.py --mode CALIBRATING --display 1 [ --additional-options <arg> ]...```

(See below for additional options)

The software should start running and pause as it's waiting for you to set the calibration through the GUI.

### Start The GUI

Go back to your second ('gui') terminal in project's 'gui' directory and type either


```MapboxAccessToken='your-Mapbox-token-here' npm run dev-localhost```
or
```MapboxAccessToken='your-Mapbox-token-here' npm run dev-external```

Choose ```npm run dev-localhost``` to ensure your GUI server is only accessible to users on this computer via the loopback (localhost/127.0.0.1) interface 

Choose ```npm run dev-external``` if you want the server to bind to all IPv4 addresses on the local machine making it also accesible to computers on your Local Area Network if you're behind a router or to *any computer* on the internet if your computer is not behind a router and is connected directly to the internet

### **Unless you know exactly what you're doing and understand the risks involved, it is highly recommended that you choose "npm run dev-localhost"**

(Instead of typing ```MapboxAccessToken='your-Mapbox-token-here'``` each time you run your GUI, you can add that line to your ~/.bashrc file to make it a permanent environment variable)


After typing the above command, Webpack will begin bundling your software and your browser will automatically open to the map via port 3000.

## Step 3: Calibrate The Node

Once the map loads, use your mouse's scroll wheel to zoom and the left and right mouse buttons to drag and rotate the map until you've adjusted your browsers view of the map to match the position and orientation of your camera in the real world. Once you've narrowed it down, click on the 'CALIBRATION' toggle button. The GUI's frame dimensions will adjust to match your camera frame's dimensions. Continue adjusting your position until it matches the position and orientation of the real precisely. 

As you're adjusting, your node should be receiving new calibration measurements and placing tracked objects on the GUI's map. Continue adjusting while referring to the node's video display until objects tracked in the video display are in their correct positions in the GUI's map.

In other words, you should have the video window that shows you the video that's streaming from the camera up on your computer screen (because the command you used to start the node included the "--display 1" option). Using your mouse, align the virtual map's viewport so it's looking from exact the same vantage point (latitiude, longitude, altitude, angle etc.) as the real camera is in real life.

Once that's done, your calibration values should be set inside the node's database. Now click the 'CALIBRATION' toggle button again to turn CALIBRATING mode off.


## Step 4: Restart The Node In 'ONLINE' Mode

Then return to your first terminal, hold down Ctrl-C on your keyboard to stop the node, then restart the node in the default mode (ONLINE)

```python multi_object_tracking.py [ --additional-options <arg> ]...``` See additional options below




## Multi Object Tracking Command Line Options:

--mode <ONLINE> | <CALIBRATING> [default: ONLINE] "If ONLINE, data is stored in main database. CALIBRATING is used for setting camera orientation in the map"
  
--display <0> | <1> [default: 0] "Displays the input video feed in console with tracked objects and bounding boxes. Useful for debugging the tracker and object detector. If not needed, do not use as it consumes uncessary computation."
  
--picamera <0> | <1> [default: 0] "DEPRECATED: By default, the computer's webcamera is used as input. If running on a Raspberry Pi, set this option to use the Pi's attached camera as input"
  
--rotation (<0> | <90> | <180> | <270>) [default: 0] "DEPRECATED: If a Raspberry Pi camera is used for input instead of the webcamera (default), this specifies camera's clockwise rotation"
  
--video <path/to/video/file> "For debugging purposes, a video file can be used as input instead of an attached webcamera (default). This specifies path to video file
  
--num_workers <#> [default: 5] "For computers with multi-core CPU's, spreads tasks into separate processes to parralelize processes and speed up software"


## Future Grassland Software Improvements
[Link to current list](https://gist.github.com/00hello/0199d393e872ed7645979f5daf7bd62c) of Grassland features and modules that will be built next


## License
#### Unless otherwise specified, this software is released under the terms of the Grassland License. It's identical to the Mozilla Public License 2.0 with the added restriction that the use of this Work or its Derivatives to gather data that comes from locations in which an uninformed third party would have no reasonable expectation of privacy is governed by our open data policy wherein all data gathered from such locations shall be made freely available to anyone with the same frequency, format and specifications to that of approved Grassland Node implementations. Approved Grassland Node implementations can be found on our Github page located here -> [https://github.com/grasslandnetwork/](https://github.com/grasslandnetwork/)

