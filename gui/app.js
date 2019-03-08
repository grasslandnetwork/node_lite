/* global window */
import React, {Component} from 'react';
import {render} from 'react-dom';
import ReactMapGL from 'react-map-gl';
import DeckGL, {PolygonLayer} from 'deck.gl';
//import {TripsLayer} from '@deck.gl/experimental-layers';
import TripsLayer from './src/client/trips-layer.js';

import {MapboxLayer} from '@deck.gl/mapbox';

import {Timepicker} from './src/client/analog-clock-timepicker/libs/timepicker.js';

import {formatTracklets} from './src/client/format-tracklets.js';


// Set your mapbox token here or set environment variable from cmd line and access using 'process.env.[variable_name]'
const MAPBOX_TOKEN = process.env.MapboxAccessToken; // eslint-disable-line

// Source data CSV
const DATA_URL = {
	BUILDINGS:
    'https://raw.githubusercontent.com/uber-common/deck.gl-data/master/examples/trips/buildings.json', // eslint-disable-line
	// TRIPS:
    // 'https://raw.githubusercontent.com/uber-common/deck.gl-data/master/examples/trips/trips.json' // eslint-disable-line
	TRIPS: './trips.json'
};

const controlsWrapper = {
	'position': 'relative',
	'zIndex': 200
}
const inlineClockStyleWrapper = {
}
const inlineClockStyle = {
	'paddingRight': '56px'
};


// [{
//   "vendor": 0,
//   "segments": [
//     [-74.20986, 40.81773, 1191],
//     [-74.20987, 40.81765, 1193.803],
//     [-74.20998, 40.81746, 1205.321],
//     [-74.21062, 40.81682, 1249.883],
//     [-74.21002, 40.81644, 1277.923],
//     [-74.21084, 40.81536, 1333.850],
//     [-74.21142, 40.8146, 1373.257],
//     [-74.20965, 40.81354, 1451.769],
//     [-74.21166, 40.81158, 1527.939],
//     [-74.21247, 40.81073, 1560.114],
//     [-74.21294, 40.81019, 1579.966],
//     [-74.21302, 40.81009, 1583.555],
//     [-74.21055, 40.80768, 1660.904],
//     [-74.20995, 40.80714, 1678.797],
//     [-74.20674, 40.80398, 1779.882],
//     [-74.20659, 40.80382, 1784.858],
//     [-74.20634, 40.80352, 1793.853],
//     [-74.20466, 40.80157, 1868.948]
//   ]
// }, {
//   "vendor": 0,
//   "segments": [
//     [-74.27508, 40.6065, 1637],
//     [-74.27419, 40.60623, 1666.166],
//     [-74.27382, 40.60689, 1679.748],
//     [-74.27364, 40.60728, 1687.573],
//     [-74.27364, 40.60738, 1689.467],
//     [-74.27368, 40.6076, 1693.672],
//     [-74.27377, 40.60786, 1698.763],
//     [-74.27257, 40.60817, 1717.431],
//     [-74.27156, 40.60842, 1733.076],
//     [-74.27146, 40.6079, 1743.274],
//     [-74.27136, 40.60737, 1753.664],
//     [-74.26967, 40.60743, 1786.261],
//     [-74.26959, 40.60665, 1799.986],
//     [-74.26721, 40.6068, 1835.563]
//   ]
// }

const LIGHT_SETTINGS = {
	lightsPosition: [-74.05, 40.7, 8000, -73.5, 41, 5000],
	ambientRatio: 0.05,
	diffuseRatio: 0.6,
	specularRatio: 0.8,
	lightsStrength: [2.0, 0.0, 0.0, 0.0],
	numberOfLights: 2
};

export const INITIAL_VIEW_STATE = {
	longitude: -75.75084956019369,
	latitude: 45.39356859484852,
	// longitude: -73.82452,
	// latitude: 40.66515,
	zoom: 21.613169643314922,
	maxZoom: 24,
	pitch: 67.27592880778502,
	maxPitch: 89.9,
	altitude: 1.5,
	bearing: 86.64185328185327
};

const mapboxBuildingLayer = {
	id: '3d-buildings',
	source: 'composite',
	'source-layer': 'building',
	filter: ['==', 'extrude', 'true'],
	type: 'fill-extrusion',
	minzoom: 14,
	'paint': {
		'fill-extrusion-color': '#aaa',
		
		// use an 'interpolate' expression to add a smooth transition effect to the
		// buildings as the user zooms in
		'fill-extrusion-height': [
			"interpolate", ["linear"], ["zoom"],
			15, 0,
			15.05, ["get", "height"]
		],
		'fill-extrusion-base': [
			"interpolate", ["linear"], ["zoom"],
			15, 0,
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

	
		// This binding is necessary to make `this` work in the callback
		this._onWebGLInitialized = this._onWebGLInitialized.bind(this);
		this._onMapLoad = this._onMapLoad.bind(this);
		this._determineCalibration = this._determineCalibration.bind(this);
		this._adjustCanvas = this._adjustCanvas.bind(this);
		// this._getTracklets = this._getTracklets.bind(this);
		this._receiveTracklets = this._receiveTracklets.bind(this);
		this._openCalFrameWebsocketConnection = this._openCalFrameWebsocketConnection.bind(this);
		this._openTrackletsWebsocketConnection = this._openTrackletsWebsocketConnection.bind(this);

		this._openCalFrameWebsocketConnection();
		this._openTrackletsWebsocketConnection();

		this._onCalibrationToggleClick = this._onCalibrationToggleClick.bind(this);
		
	}

	componentDidMount() {
		this._animate();
		this.ws_send_cal_recv_frame.addEventListener('message', this._adjustCanvas)
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
			this.ws_send_cal_recv_frame = new WebSocket('ws://localhost:8080/send_calibration');
		} catch (e) {
			console.log("error", e);
		}
	}

	_openTrackletsWebsocketConnection() {
		try {
			console.log("Reconnecting to ws_get_tracklets");
			this.ws_get_tracklets = new WebSocket('ws://localhost:8080/get_tracklets');
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

		if (!this.state.calibrationMode) return null;
		
		// console.log(viewState);

		const {bearing, pitch, zoom, latitude, longitude, width, height} = viewState;
		const map = this._map;
		// var bearing = map.getBearing();
		// var pitch = map.getPitch();
		// var zoom = map.getZoom();
		
		// Not the location of the camera but the geographic focal point according to the mapbox/OSM camera
		// var lnglat_focus = map.getCenter();
		// var lng_focus = lnglat_focus.lng;
		// var lat_focus = lnglat_focus.lat;

		var lng_focus = longitude;
		var lat_focus = latitude;
		
		// Homography points
		var homography_points = {};
		
		// var canvas = map.getCanvas(),
		// 	w = canvas.width,
		// 	h = canvas.height;

		const w = width;
		const h = height;
		
		// The modification made to mapbox (https://github.com/mapbox/mapbox-gl-js/issues/3731#issuecomment-368641789) that allows a greater than 60 degree pitch has a bug with unprojecting points closer to the horizon. They get very "screwy". So the two top homography_point corners in the web app ('ul' and 'ur') actually start half way down the canvas as the starting point to start from below the horizon
		const b_h = h/2 
		
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

	// _getTracklets() {

	// 	if (this.state.trackableObjectsArray.length == 0) {

	// 		if (this.clockTimestamp < this.last_query_timestamp || this.clockTimestamp > this.last_query_timestamp+this.query_timestamp_range-1000) {
	// 			this.waitingToReceiveTrackableObjects = true;
	// 			this.new_query_timestamp = this.timepicker.getTimestamp();
	// 			// if (this.ws_get_tracklets.readyState !== 1 ){
	// 			// 	console.log(this.ws_get_tracklets.readyState);
	// 			// }
	// 			if (this.ws_get_tracklets.readyState == 1) {
	// 				this.ws_get_tracklets.send(JSON.stringify({"timestamp": this.new_query_timestamp, "range": this.query_timestamp_range})); // ask server for the first trackableObjects
	// 			} else if (this.ws_get_tracklets.readyState == 3) { // if it's closed, reopen
	// 				this._openTrackletsWebsocketConnection();
	// 			}

	// 		}

		 
	// 		//return null;
	// 	}
		
	// }

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
			animationSpeed = 30 // unit time per second
		} = this.props;

		this.loopLength = loopLength;
		this.loopTime = loopLength / animationSpeed;
		
		
		// find out how long it's been since this was last called
		var elapsedMilliseconds = rAFTimestamp - this.lastRAFTimestamp;
		// move clock's time forward by {elapsedMilliseconds}
		this.clockTimestamp = this.timepicker.moveClockDateForward(elapsedMilliseconds);
		// console.log(this.getDateString());

		
		//const timestamp = Date.now() / 1000;
		const timestamp = this.clockTimestamp / 1000;
		this.setState({
			time: ((timestamp % this.loopTime) / this.loopTime) * loopLength
		});

		// this.setState({
		// 	time: this.clockTimestamp / 1000
		// });


		if (this.mapLoaded) { // if the map is loaded 
			
			if (!this.waitingToReceiveTrackableObjects) { // if we're not currently waiting on a request for more trackableObjects

				// this._getTracklets();

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

	_renderLayers() {
		const {buildings = DATA_URL.BUILDINGS, trips = DATA_URL.TRIPS, trailLength = 180} = this.props;


		return [
			new TripsLayer({
				id: 'tracklets',
				data: this.state.trackableObjectsArray,
				getPath: d => d.tracklets,
				getColor: d => (d.vendor === 0 ? [253, 128, 93] : [23, 184, 190]),
				opacity: 0.3,
				strokeWidth: 2,
				trailLength,
				currentTime: this.state.time
			})    ];
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

		// map.addLayer(new MapboxLayer({id: 'my-scatterplot', deck}));
		map.addLayer(mapboxBuildingLayer);

	}


	render() {
		const {gl} = this.state;
		const {viewState, controller = true, baseMap = true} = this.props;

		return (
			
			<React.Fragment>
				<div style={controlsWrapper}>
				<div style={inlineClockStyleWrapper}>
				<div id="timepicker" style={inlineClockStyle}>
				</div>
				</div>

				<label className="calibrationToggleBox">
				<input type="checkbox" onClick={this._onCalibrationToggleClick} />
				<span className="calibrationToggle"></span>
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
