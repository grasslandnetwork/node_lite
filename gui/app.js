/* global window */
import React, {Component} from 'react';
import {render} from 'react-dom';
import ReactMapGL from 'react-map-gl';
import DeckGL, {PolygonLayer, GeoJsonLayer} from 'deck.gl';
// PolygonLayer, GeoJsonLayer etc. can't be used until mapbox-gl is upgraded to at least 50.0 (See note in webpack-config.js)
//import {TripsLayer} from '@deck.gl/experimental-layers';
import TripsLayer from './src/client/trips-layer.js';

import {MapboxLayer} from '@deck.gl/mapbox'; // can't be used until mapbox-gl is upgraded to at least 50.0 (See note in webpack-config.js)

import {Timepicker} from './src/client/analog-clock-timepicker/libs/timepicker.js';

import {formatTracklets} from './src/client/format-tracklets.js';
import {interpolatePositionAndBearing} from './src/client/format-tracklets.js';
import cheapRuler from 'cheap-ruler';

import {polygon as turfPolygon} from '@turf/turf';
import {transformRotate as turfTransformRotate} from '@turf/turf';
import {transformTranslate as turfTransformTranslate} from '@turf/turf';



// Set your mapbox token here or set environment variable from cmd line and access using 'process.env.[variable_name]'
const MAPBOX_TOKEN = process.env.MapboxAccessToken; // eslint-disable-line


// Source demo data JSON. Change to use different demo data
const DATA_URL = {
	DEMO_TRACKLETS: './demo_nyc_tracklets.json'  // eslint-disable-line
};
const trackletsData = require('./demo_nyc_tracklets.json');

// change DEMO_MODE to true to use demo data. Change INITIAL_VIEW_STATE latitude/longitude values to location of demo data
const DEMO_MODE = false;


const controlsWrapper = {
	'position': 'relative',
	'zIndex': 200
}
const inlineClockStyleWrapper = {
}
const inlineClockStyle = {
	'paddingRight': '56px'
};

const LIGHT_SETTINGS = {
	lightsPosition: [-74.05, 40.7, 8000, -73.5, 41, 5000],
	ambientRatio: 0.05,
	diffuseRatio: 0.6,
	specularRatio: 0.8,
	lightsStrength: [2.0, 0.0, 0.0, 0.0],
	numberOfLights: 2
};

export const INITIAL_VIEW_STATE = {
	longitude: 0,
	latitude: 0,
	zoom: 1,
	maxZoom: 24,
	pitch: 0,
	maxPitch: 89.9,
	altitude: 1.5,
	bearing: 0
};

const mapboxBuildingLayer = {
	id: '3d-buildings',
	source: 'composite',
	'source-layer': 'building',
	filter: ['==', 'extrude', 'true'],
	type: 'fill-extrusion',
	minzoom: 13,
	'paint': {
		'fill-extrusion-color': '#aaa',
		
		// use an 'interpolate' expression to add a smooth transition effect to the
		// buildings as the user zooms in
		'fill-extrusion-height': [
			"interpolate", ["linear"], ["zoom"],
			13, 0,
			15.05, ["get", "height"]
		],
		'fill-extrusion-base': [
			"interpolate", ["linear"], ["zoom"],
			13, 0,
			15.05, ["get", "min_height"]
		],
		'fill-extrusion-opacity': .6
	}
	
};



export default class App extends Component {
	constructor(props) {
		super(props);
		this.state = {
			time: 0,
			trackableObjectsArray: [],
			canvasWidth: window.innerWidth,
			canvasHeight: window.innerHeight,
			calibrationMode: false
		};

		this.timepicker = new Timepicker();
		this.waitingToReceiveTrackableObjects = false;
		this.clockTimestamp;
		this.last_query_timestamp = 0;
		this.new_query_timestamp;
		this.query_timestamp_range = 60000;
		this.mapLoaded = false;
		this.lastRAFTimestamp = 0;
		this.lastMapLatitudeFocus = 0;
		this.currentZoomLevel = INITIAL_VIEW_STATE.zoom;
		this.trackedObjectMinZoomAppearance = 10;

		this.defaultFootprint = {};

		// This binding is necessary to make `this` work in the callback
		this._onWebGLInitialized = this._onWebGLInitialized.bind(this);
		this._onMapLoad = this._onMapLoad.bind(this);
		this._determineCalibration = this._determineCalibration.bind(this);
		this._adjustCanvas = this._adjustCanvas.bind(this);
		this._receiveTracklets = this._receiveTracklets.bind(this);
		this._interpolateTrackableObjects = this._interpolateTrackableObjects.bind(this);
		this._openCalFrameWebsocketConnection = this._openCalFrameWebsocketConnection.bind(this);
		this._openTrackletsWebsocketConnection = this._openTrackletsWebsocketConnection.bind(this);

		this._openCalFrameWebsocketConnection();
		this._openTrackletsWebsocketConnection();

		this._onCalibrationToggleClick = this._onCalibrationToggleClick.bind(this);
		this._setDefaultObjectFootprints = this._setDefaultObjectFootprints.bind(this);

		this._setDefaultObjectFootprints(1); // person
		this._setDefaultObjectFootprints(3); // car
		
	}

	componentDidMount() {
		this._animate();
		this.ws_send_cal_recv_frame.addEventListener('message', this._adjustCanvas);
		this.ws_get_tracklets.addEventListener('message', this._receiveTracklets);
		
		this.ws_send_cal_recv_frame.addEventListener('close', this._openCalFrameWebsocketConnection);
		this.ws_get_tracklets.addEventListener('close', this._openTrackletsWebsocketConnection);
		
		document.getElementById('timepicker').appendChild(this.timepicker.getElement());
		this.timepicker.show();
	}

	componentWillUnmount() {
		this.timepicker.destroy();
		if (this._animationFrame) {
			window.cancelAnimationFrame(this._animationFrame);
		}
		this.ws_send_cal_recv_frame.removeEventListener('message', this._adjustCanvas);
		this.ws_get_tracklets.removeEventListener('message', this._receiveTracklets);

		this.ws_send_cal_recv_frame.removeEventListener('close', this._openCalFrameWebsocketConnection);
		this.ws_get_tracklets.removeEventListener('close', this._openTrackletsWebsocketConnection);

	}


	_openCalFrameWebsocketConnection() {
		try {
			this.ws_send_cal_recv_frame = new WebSocket('ws://'+window.location.hostname+':8080/send_calibration');
		} catch (e) {
			console.log("error", e);
		}
	}

	_openTrackletsWebsocketConnection() {
		try {
			console.log("Reconnecting to ws_get_tracklets");
			this.ws_get_tracklets = new WebSocket('ws://'+window.location.hostname+':8080/get_tracklets');
		} catch(e) {
			console.log("error", e);
		}
	}


	_onCalibrationToggleClick() {

		if (this.state.calibrationMode) { // if we are CURRENTLY in calibration mode
			this.setState({
				canvasWidth: window.innerWidth,
				canvasHeight: window.innerHeight,
				calibrationMode: false
			});
		} else { // if we're NOT CURRENTLY in calibration mode
			this.setState({
				calibrationMode: true
			});
		}

	}

	_setDefaultObjectFootprints(category = 1) {

		var lat_dst;
		var lng_dst;
		var origin_dst;

		// Declare length/width of all object objects of that category (in lat and lng values)
		if (category == 1) { // person
			
			lat_dst = 0.00000492271;
			lng_dst = 0.00000628327;
			
		} else if (category == 3) { // car

			lat_dst = 0.00004556421;
			lng_dst = 0.00002992647;
			
		}

		// Assume position coordinates relative to the object itself is located in the center with respect to the ground plane
		// Assume a view that has a north/south orientation

		// Mapbox bearing angles are in degrees rotating counter-clockwise from north
		// Thus, the right half of the (x,y) plane has negative angles
		// Assume the object is on an (x,y) plane with 'y' being north and the origin being the object's center (the 'position')
		// So along the 'y'/north-south axis the distance between the object's center and its points is lat_dst/2 
		// And along the 'x'/east-west axis, the distance between the objec's center and it's pionts is lng_dst/2

		//Get the distance of each of the four corners from the origin for our hypotenuse... a^2 + b^2 = c^2
		origin_dst = Math.sqrt( Math.pow((lat_dst/2), 2) + Math.pow((lng_dst/2), 2) );

		// get the angle theta (in degrees) of each corner
		var tr_deg = Math.acos( (lat_dst/2) / origin_dst ) * 180 / Math.PI;
		var br_deg = Math.acos( -(lat_dst/2) / origin_dst ) * 180 / Math.PI;
		var bl_deg = Math.acos( -(lat_dst/2) / origin_dst ) * 180 / Math.PI;
		var tl_deg = Math.acos( (lat_dst/2) / origin_dst ) * 180 / Math.PI;

		
		this.defaultFootprint[category] = {
			"lat_dst": lat_dst,
			"lng_dst": lng_dst,
			"origin_dst": origin_dst,
			"tr_deg": tr_deg,
			"br_deg": br_deg,
			"bl_deg": bl_deg,
			"tl_deg": tl_deg
		};

	}

	_moduloBearing(x) {
		
		// if it's greater than +180, it should be -180 + (x % 180 )
		if (x > 180) {
			return -180 + (x % 180);
		}
		
		// if it's smaller than -180, it should be 180 - (Math.abs(x) % 180)
		if (x < -180) {
			return 180 - (Math.abs(x) % 180);
		}
		
	}


	_objectFootprint(positionAndBearing, category=1) {

		// // add the new bearing to the current angle of each corner
		// var new_tr_deg = this._moduloBearing(this.defaultFootprint[category].tr_deg + positionAndBearing[1]);
		// var new_br_deg = this._moduloBearing(this.defaultFootprint[category].br_deg + positionAndBearing[1]);
		// var new_bl_deg = this._moduloBearing(this.defaultFootprint[category].bl_deg + positionAndBearing[1]);
		// var new_tl_deg = this._moduloBearing(this.defaultFootprint[category].tl_deg + positionAndBearing[1]);


		// // Multiply the distance from the origin by the cosine of each new degree to get the new displacement along the 'y' (latitude) axis
		// var tr_lat_displacement = this.defaultFootprint[category].origin_dst * Math.cos(new_tr_deg*Math.PI/180)
		// var br_lat_displacement = this.defaultFootprint[category].origin_dst * Math.cos(new_br_deg*Math.PI/180)
		// var bl_lat_displacement = this.defaultFootprint[category].origin_dst * Math.cos(new_bl_deg*Math.PI/180)
		// var tl_lat_displacement = this.defaultFootprint[category].origin_dst * Math.cos(new_tl_deg*Math.PI/180)

		// // Multiply the distance from the origin by the sine of each new degree to get the new displacement along the 'x' (longitude) axis
		// var tr_lng_displacement = this.defaultFootprint[category].origin_dst * Math.sin(new_tr_deg*Math.PI/180)
		// var br_lng_displacement = this.defaultFootprint[category].origin_dst * Math.sin(new_br_deg*Math.PI/180)
		// var bl_lng_displacement = this.defaultFootprint[category].origin_dst * Math.sin(new_bl_deg*Math.PI/180)
		// var tl_lng_displacement = this.defaultFootprint[category].origin_dst * Math.sin(new_tl_deg*Math.PI/180)
		
		var top_right;
		var bottom_right;
		var bottom_left;
		var top_left;
		
		// top_right = { "lat": positionAndBearing[0].lat + tr_lat_displacement, "lng": positionAndBearing[0].lng + tr_lng_displacement };
		// bottom_right = { "lat": positionAndBearing[0].lat + br_lat_displacement, "lng": positionAndBearing[0].lng + br_lng_displacement };
		// bottom_left = { "lat": positionAndBearing[0].lat + bl_lat_displacement, "lng": positionAndBearing[0].lng + bl_lng_displacement };
		// top_left = { "lat": positionAndBearing[0].lat + tl_lat_displacement, "lng": positionAndBearing[0].lng + tl_lng_displacement };


		top_right = [ positionAndBearing[0].lng + (this.defaultFootprint[category].lng_dst/2), positionAndBearing[0].lat + (this.defaultFootprint[category].lat_dst/2) ];

		bottom_right = [ positionAndBearing[0].lng + (this.defaultFootprint[category].lng_dst/2), positionAndBearing[0].lat - (this.defaultFootprint[category].lat_dst/2) ];

		bottom_left = [ positionAndBearing[0].lng - (this.defaultFootprint[category].lng_dst/2), positionAndBearing[0].lat - (this.defaultFootprint[category].lat_dst/2) ];

		top_left = [ positionAndBearing[0].lng - (this.defaultFootprint[category].lng_dst/2), positionAndBearing[0].lat + (this.defaultFootprint[category].lat_dst/2) ];
		
		
		var poly = turfPolygon(
			[
				[
					top_right,
					bottom_right,
					bottom_left,
					top_left,
					top_right
				]
			]
		);

		// console.log(positionAndBearing[1]);

		var rotatedPoly = turfTransformRotate(poly, positionAndBearing[1]);

		if (DEMO_MODE) {
			var translatedPoly = turfTransformTranslate(rotatedPoly, 3, positionAndBearing[1]+90, {"units": "meters"});
			return translatedPoly.geometry.coordinates;
		}

		return rotatedPoly.geometry.coordinates;
				
		// // Return coordinates
		// return [
		// 	[
		// 		[
		// 			top_right.lng,
		// 			top_right.lat
		// 		],
		// 		[
		// 			bottom_right.lng,
		// 			bottom_right.lat
		// 		],
		// 		[
		// 			bottom_left.lng,
		// 			bottom_left.lat
		// 		],
		// 		[
		// 			top_left.lng,
		// 			top_left.lat
		// 		],
		// 		[
		// 			top_right.lng,
		// 			top_right.lat
		// 		]
		// 	]	 
		// ]

		
	}


	_adjustCanvas(message) {

		console.log("Map received frame dim");
		// console.log(m.data);
		const frame_dim = JSON.parse(message.data);

		const nodeFrameWidth = Math.round(frame_dim.width);
		const nodeFrameHeight = Math.round(frame_dim.height);

		this.setState({
			canvasWidth: nodeFrameWidth,
			canvasHeight: nodeFrameHeight 
		});


	}

	_determineCalibration({viewState, interactionState, oldViewState}) {

		// console.log(viewState);

		const {bearing, pitch, zoom, latitude, longitude, width, height} = viewState;
		
		this.currentZoomLevel = zoom;

		// const map = this._map;
		// var bearing = map.getBearing();
		// var pitch = map.getPitch();
		// var zoom = map.getZoom();
		
		// Not the location of the camera but the geographic focal point according to the mapbox/OSM camera
		// var lnglat_focus = map.getCenter();
		// var lng_focus = lnglat_focus.lng;
		// var lat_focus = lnglat_focus.lat;

		var lng_focus = longitude;
		var lat_focus = latitude;

		
		// (From docs) ...create a ruler object only once per a general area of calculation, and then reuse it as much as possible. Don't create a new ruler for every calculation.
		if (Math.abs(this.lastMapLatitudeFocus - lat_focus) > 0.05) { 
			// Create a Cheap Ruler object that will approximate measurements around the given latitude.
			this.ruler  = cheapRuler(lat_focus, 'meters');
			
			this.lastMapLatitudeFocus = lat_focus; // set lastMapLatitudeFocus to the new focus
		}


		if (!this.state.calibrationMode) return null; // If we're not in CALIBRATION mode, no need to continue
		

		const map = this._map;
		
		// Homography points
		var homography_points = {};
		
		// var canvas = map.getCanvas(),
		// 	w = canvas.width,
		// 	h = canvas.height;

		const w = width;
		const h = height;
		
		// The modification made to mapbox (https://github.com/mapbox/mapbox-gl-js/issues/3731#issuecomment-368641789) that allows a greater than 60 degree pitch has a bug with unprojecting points closer to the horizon. They get very "screwy". So the two top homography_point corners in the web app ('ul' and 'ur') actually start half way down the canvas as the starting point to start from below the horizon
		const b_h = h/2;
		
		const cUL = map.unproject([0,0]).toArray(),
		cUR = map.unproject([w,0]).toArray(),
		cLR = map.unproject([w,h]).toArray(),
		cLL = map.unproject([0,h]).toArray();
		homography_points['corners'] = {};
		homography_points['corners']['ul'] = { lng: map.unproject([0,b_h]).lng, lat: map.unproject([0,b_h]).lat };
		homography_points['corners']['ur'] = { lng: map.unproject([w,b_h]).lng, lat: map.unproject([w,b_h]).lat };
		homography_points['corners']['ll'] = { lng: map.unproject([w,h]).lng, lat: map.unproject([w,h]).lat };
		homography_points['corners']['lr'] = { lng: map.unproject([0,h]).lng, lat: map.unproject([0,h]).lat };

		homography_points['markers'] = {};
		
		const calibration = {
			bearing: bearing,
			pitch: pitch,
			zoom: zoom,
			lng_focus: lng_focus,
			lat_focus: lat_focus,
			homography_points: homography_points
		};


		if (this.ws_send_cal_recv_frame.readyState == 1) {
			this.ws_send_cal_recv_frame.send(JSON.stringify(calibration));
		} else if (this.ws_send_cal_recv_frame.readyState == 3) { // if it's closed, reopen
			this._openCalFrameWebsocketConnection();
		}

	}


	_receiveTracklets(message) {

		// console.log("tracklets received");

		// always assign newly received tracklets to trackableObjectsArray so it's reflects the tracklets that are in the clock's range
		this.setState({
			trackableObjectsArray: formatTracklets(JSON.parse(message.data), this.loopTime, this.loopLength) 
		});

		if (this.state.trackableObjectsArray.length > 0) console.log(this.state.trackableObjectsArray);

		
		this.last_query_timestamp = this.new_query_timestamp; // set the last_query_timestamp
		this.waitingToReceiveTrackableObjects = false;
	}

	_animate(rAFTimestamp=0) {
		const {
			loopLength = 1800, // unit corresponds to the timestamp in source data
			animationSpeed = 7 // unit time per second
		} = this.props;

		this.loopLength = loopLength;
		this.loopTime = loopLength / animationSpeed;
		
		
		// find out how long it's been since this was last called
		var elapsedMilliseconds = rAFTimestamp - this.lastRAFTimestamp;
		// move clock's time forward by {elapsedMilliseconds}
		this.clockTimestamp = this.timepicker.moveClockDateForward(elapsedMilliseconds);

		if (DEMO_MODE) {
			const timestamp = this.clockTimestamp / 1000;
			this.setState({
				time: ((timestamp % this.loopTime) / this.loopTime) * loopLength
			});
		} else {
			this.setState({
				time: this.clockTimestamp
			});
		}


		if (this.mapLoaded) { // if the map is loaded

			// calculate the next interpolated position of each trackable object
			if (DEMO_MODE) {
				this.state.trackableObjectsArray = trackletsData;
			}
			
			this._interpolateTrackableObjects(this.state.trackableObjectsArray);
			
			if (!DEMO_MODE && !this.waitingToReceiveTrackableObjects) { // if we're NOT in DEMO_MODE and NOT currently waiting on a request for more trackableObjects

				if (this.clockTimestamp < this.last_query_timestamp+15000 || this.clockTimestamp > this.last_query_timestamp+this.query_timestamp_range-15000)  { // we'll still get back the range of tracklets. This just makes sure we don't experience a gap while we're waiting

					this.waitingToReceiveTrackableObjects = true;
					if (this.clockTimestamp < this.last_query_timestamp+15000) { // if clock is being dragged backwards, set query back
						this.new_query_timestamp = this.clockTimestamp-30000;
					} else {
						this.new_query_timestamp = this.clockTimestamp;
					}

					if (this.ws_get_tracklets.readyState == 1) {
						this.ws_get_tracklets.send(JSON.stringify({"timestamp": this.new_query_timestamp, "range": this.query_timestamp_range})); // ask server for more trackableObjects
					} else if (this.ws_get_tracklets.readyState == 3) { // if it's closed, reopen
						this._openTrackletsWebsocketConnection();
					}


					setTimeout(function(){ this.waitingToReceiveTrackableObjects = false; }, 4000); // set timeout to change waitingToReceiveTrackableObjects to false just in case something happens and the event listener is never fired changing waitingToReceiveTrackableObjects back to false

				}
			}

		}

		// set this current rAFTimestamp as the last one for next time
		this.lastRAFTimestamp = rAFTimestamp;
			
		this._animationFrame = window.requestAnimationFrame(this._animate.bind(this));
	}

	
	_interpolateTrackableObjects(trackableObjectsArray) {
		
		// if this.ruler isn't set or the zoom level is too low
		if (this.ruler === undefined || this.currentZoomLevel < this.trackedObjectMinZoomAppearance) return null;

		const featureCollection = []; // make new array to hold these Objects and interpolated positions
		
		for(var i=0; i < trackableObjectsArray.length-1; i++) {

			
			var inMilliseconds;
			if (DEMO_MODE) {
				inMilliseconds = false;
			} else {
				inMilliseconds = true;
			}
			// get the position
			var positionAndBearing = interpolatePositionAndBearing(trackableObjectsArray[i]['tracklets'], this.state.time, this.ruler, inMilliseconds);

			if (positionAndBearing[0] !== null) {

				featureCollection.push({
					"type": "Feature",
					"geometry": {
						"coordinates": this._objectFootprint(positionAndBearing, 3),
						"type": "Polygon"
					},
					"properties":{
						"category": "car",
						"id": trackableObjectsArray[i]["object_id"],
						"height": 2,
						"color": "rgb(255, 0, 0)"
					}
				});
			}
		}

		this._map.getSource('trackedObject').setData(
			{
				"type": "FeatureCollection",
				"features": featureCollection
			}
		);

		
	}

	_renderLayers() {
		const {tracklets = DATA_URL.DEMO_TRACKLETS, trailLength = 50} = this.props;


		// const geojson_ = {
		// 	"type": "Feature",
		// 	"geometry": {
		// 		"coordinates": this._objectFootprint([{"lng": -74.20992, "lat": 40.81773}, 0]),
		// 		"type": "Polygon"
		// 	},
		// 	"properties":{
		// 		"type":"person",
		// 		"id":"20092as9df2",
		// 		"height": 2,
		// 		"color": "rgb(0, 255, 0)"
		// 	}
		// }

		// const geoJsonData = {
		// 	"type":"FeatureCollection",
		// 	"features":[ geojson_ ]
		// };

		
		// const thisTrackedObjectsLayer = new GeoJsonLayer({
		// 	id: 'geojson-layer',
		// 	geoJsonData,
		// 	pickable: true,
		// 	stroked: false,
		// 	filled: true,
		// 	extruded: true,
		// 	lineWidthScale: 20,
		// 	lineWidthMinPixels: 2,
		// 	getFillColor: [160, 160, 180, 200],
		// 	getLineColor: d => colorToRGBArray(d.properties.color),
		// 	getRadius: 100,
		// 	getLineWidth: 1,
		// 	getElevation: 30,
		// });


		return [

			new TripsLayer({
                id: 'tracklets',
                data: this.state.trackableObjectsArray,
				getPath: d => d.tracklets,
				getColor: d => (d.detection_class_id === 0 ? [255, 0, 0] : [0, 255, 0]),
				opacity: 0.3,
				strokeWidth: 2,
				trailLength,
				currentTime: this.state.time
			})

		];
	}

	// DeckGL and mapbox will both draw into this WebGL context
	_onWebGLInitialized(gl) {
		this.setState(state => ({
			gl
		}));
	}

	_onMapLoad() {
		this.mapLoaded = true;
		
		const map = this._map;
		const deck = this._deck;

		//map.addLayer(new MapboxLayer({id: 'geojson-layer', deck}));
		map.addLayer(mapboxBuildingLayer);

		
		// See https://www.mapbox.com/mapbox-gl-js/example/point-from-geocoder-result/
		map.addSource(
			'trackedObject',
			{
				type: 'geojson',
				"data": {
					"type": "FeatureCollection",
					"features": []
				}
			}
		);

		
		// See https://www.mapbox.com/mapbox-gl-js/example/point-from-geocoder-result/
		map.addLayer({
			"id": "trackedObject",
			"type": "fill-extrusion",
			"source": "trackedObject",
			'paint': {
				'fill-extrusion-color': ["get", "color"],
				
				// modify 'interpolate' expression to add a smooth size transition effect to the
				// tracked objects as the camera zooms in
				'fill-extrusion-height': [
					"interpolate", ["linear"], ["zoom"],
					this.trackedObjectMinZoomAppearance, 0,
					15.05, ["get", "height"]
				],
				'fill-extrusion-base': [
					"interpolate", ["linear"], ["zoom"],
					this.trackedObjectMinZoomAppearance, 0,
					15.05, 0
				],
				'fill-extrusion-opacity': .6
			}

		});


		var geojson_ = {
			"type": "Feature",
			"geometry": {
				"coordinates": this._objectFootprint([{"lng": -74.20986, "lat": 40.81773}, 0]),
				"type": "Polygon"
			},
			"properties":{
				"type":"person",
				"id":"20092as9df2",
				"height": 2,
				"color": "rgb(0, 255, 0)"
			}
		};

		
		map.getSource('trackedObject').setData(
			{
				"type": "FeatureCollection",
				"features": [geojson_]
			}
		);

	}


	render() {
		const {gl} = this.state;
		const {viewState, controller = true, baseMap = true} = this.props;

		return (
			
			<React.Fragment>
				<div style={controlsWrapper}>
				<div id="timepicker" style={inlineClockStyle}>
				</div>


				<label className="switch">
				<input type="checkbox" id="togBtn" onClick={this._onCalibrationToggleClick} />
				<div className="slider round">
				<span className="on">CALIBRATION MODE ON</span>
				<span className="off">CALIBRATION MODE OFF</span>
				</div>
				</label>

				</div>

				<DeckGL
				ref={ref => {
					// save a reference to the Deck instance
					this._deck = ref && ref.deck;
				}}
				layers={this._renderLayers()}
				initialViewState={INITIAL_VIEW_STATE}
				viewState={viewState}
				width={this.state.canvasWidth}
				height={this.state.canvasHeight}
				controller={controller}
				onWebGLInitialized={this._onWebGLInitialized}
				onViewStateChange={this._determineCalibration}
				>
				{gl && (<ReactMapGL
						ref={ref => {
							// save a reference to the mapboxgl.Map instance
							this._map = ref && ref.getMap();
						}}
						gl={gl}
						reuseMaps
						mapStyle="mapbox://styles/mapbox/light-v9"
						preventStyleDiffing={true}
						visibilityConstraints={ {minZoom: 0, maxZoom: 24, minPitch: 0, maxPitch: 89.9} }
						mapboxApiAccessToken={MAPBOX_TOKEN}
						onLoad={this._onMapLoad}
						/>
				)}
			    </DeckGL>
			</React.Fragment>

		);
	}
}

export function renderToDOM(container) {
	render(<App />, container);
}
