# Grassland Node_Lite

### A Grassland mining node that can run on mini computers or older desktops and laptops. This repo is the client side to the Serverless [Node Lite Object Detection](https://github.com/grasslandnetwork/node_lite_object_detection) AWS Lambda function which handles the node's object detections. 

### Installation
#### Requires at least 4 GB's of RAM and Python 3.6 or greater. It's recommended that you use a Python virtual environment

Clone this repo on your own machine. 'cd' to the project's root directory and install the required modules using

```pip install -r requirements.txt```

### Running Your Node
You'll need to calibrate your node the first time you run it. So we'll also need to load the node's GUI (graphical user interface) which helps you visually calibrate the orientation of the node's camera in the real world.

Before we start the node, open a second bash terminal and cd to the projects 'gui' subfolder.

```cd gui```

This module uses Node.js version 8.10 or higher. If you have Node.js on your computer, in your terminal, type
```npm install```

To use the map, you will need a free Mapbox Access Token. You can get a free Mapbox Access token here -> https://docs.mapbox.com/help/glossary/access-token/


Once you've received your Mapbox token make a note of it and then return to the first terminal to start your node. Type

```python multi_object_tracking.py --mode CALIBRATING display 1 [ --additional-options <arg> ]...```

--Options <Arguments> Description
  --mode <ONLINE> | <CALIBRATING> [default: ONLINE] "If ONLINE, data is stored in main database. CALIBRATING is used for setting camera orientation in the map"
  
  --display <0> | <1> [default: 0] "Displays the input video feed in console with tracked objects and bounding boxes. Useful for debugging the tracker and object detector. If not needed, do not use as it consumes uncessary computation."
  
  --picamera <0> | <1> [default: 0] "DEPRECATED: By default, the computer's webcamera is used as input. If running on a Raspberry Pi, set this option to use the Pi's attached camera as input"
  
  --rotation (<0> | <90> | <180> | <270>) [default: 0] "DEPRECATED: If a Raspberry Pi camera is used for input instead of the webcamera (default), this specifies camera's clockwise rotation"
  
  --video <path/to/video/file> "For debugging purposes, a video file can be used as input instead of an attached webcamera (default). This specifies path to video file
  
  --num_workers <#> [default: 5] "For computers with multi-core CPU's, spreads tasks into separate processes to parralelize processes and speed up software"

The software should start running and pause as it's waiting for you to set the calibration. Go back to your second ('gui') terminal in project's 'gui' directory and type either


```MapboxAccessToken='your-Mapbox-token-here' npm run dev-localhost```
or
```MapboxAccessToken='your-Mapbox-token-here' npm run dev-external```

Choose ```npm run dev-localhost``` to ensure your GUI server is only accessible to users on this computer via the loopback (localhost/127.0.0.1) interface 

Choose ```npm run dev-external``` if you want the server to bind to all IPv4 addresses on the local machine making it also accesible to computers on your Local Area Network if you're behind a router or to *any computer* on the internet if your computer is not behind a router and is connected directly to the internet

### **Unless you know exactly what you're doing and understand the risks involved, it is highly recommended that you choose "npm run dev-localhost"**

(Instead of typing ```MapboxAccessToken='your-Mapbox-token-here'``` each time you run your GUI, you can add that line to your ~/.bashrc file to make it a permanent environment variable)


After typing the above command, Webpack will begin bundling your software and your browser will automatically open to the map via port 3000. 

Once the map loads, use your mouse's scroll wheel to zoom and the left and right mouse buttons to drag and rotate the map until you've adjusted your browsers view of the map to match the position and orientation of your camera in the real world. Once you've narrowed it down, click on the 'CALIBRATION' toggle button. The GUI's frame dimensions will adjust to match your camera frame's dimensions. Continue adjusting your position until it matches the position and orientation of the real precisely. 

As you're adjusting, your node should be receiving new calibration measurements and placing tracked objects on the GUI's map. Continue adjusting while referring to the node's video display until objects tracked in the video display are in their correct positions in the GUI's map. Once that's done, click the 'CALIBRATION' toggle button again to turn CALIBRATING mode off.

Then return to your first terminal, hold down Ctrl-C on your keyboard to stop the node, then restart the node in the default mode (ONLINE)

```python multi_object_tracking.py [ --additional-options <arg> ]...``` See options above





#### Unless otherwise specified, this software is released under the terms of the Grassland License. It's identical to the Mozilla Public License 2.0 with the added restriction that the use of this Work or its Derivatives to gather data that comes from locations in which an uninformed third party would have no reasonable expectation of privacy is governed by our open data policy wherein all data gathered from such locations shall be made freely available to anyone with the same frequency, format and specifications to that of approved Grassland Node implementations. Approved Grassland Node implementations can be found on our Github page located here -> [https://github.com/grasslandnetwork/](https://github.com/grasslandnetwork/)
