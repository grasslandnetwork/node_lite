#!/usr/bin/env node
'use strict';

const net = require('net');
const express = require('express')

// const app = express()
const port = 8080

var expressWs = require('express-ws')
var expressWs = expressWs(express());
var app = expressWs.app;


var calibration;



app.use(express.static('dist'))

// Use this server to send calibration values received from map/browser down to node and ...
// ... send frame dimensions (frame_dim) received from node up to map/browser
app.ws('/send_calibration', (ws, req) => {
	// console.error('websocket connection from browser');
	// for (var t = 0; t < 3; t++)
	//   setTimeout(() => ws.send('Map, the server received your message', ()=>{}), 1000*t);

	ws.on('message', function incoming(message) {
		
		// console.log('Server received calibration from map');
		
		// Setting 'calibration' variable to calibration value
		calibration = message;

		// Create new socket and connect to node
		var client = new net.Socket();
		client.setTimeout(4000);
		client = client.setEncoding('utf8');
		client.connect(8765, '127.0.0.1', function() {
			// console.log('Connected to node calibration socket server');

			// Send calibration to node's websocket/socket server
			var if_sent = client.write(calibration);
			if (if_sent) {
				// console.log("Calibration sent");
			}
		});

		
		let chunks = []; // https://stackoverflow.com/a/45030133/8941739			
		client.on('data', function(data) {
			chunks.push(data); // https://stackoverflow.com/a/45030133/8941739
		}).on('end', function() {
			if (chunks.length > 0) {
				// console.log("Received frame dimensions (frame_dim) ...");
				let this_data = chunks.join("");
				var parsed_data = JSON.parse(this_data.replace(/\'/g, '"'));
				// console.log(parsed_data);
				// Send frame_dim to browser
				ws.send(JSON.stringify(parsed_data));
			}
			client.destroy(); // kill client after server's response
		});

		client.on('error', function(ex) {
			// console.log("Something happened trying to send calibration to node ");
			client.destroy(); // kill client after error
			// console.log(ex);
		});

		client.on('timeout', function() {
			console.log('calibration socket timeout');
			client.destroy(); // have to .destroy() on timeout. If just .end(), it won't reconnect if user doesn't refresh browser
		});


	});
});





// When browser requests tracklets, get them from node and return them
// Browser requests tracklets from server. Server gets them from Node. Server sends tracklets to browser
app.ws('/get_tracklets', (ws, req) => {

	// console.log("called get_tracklets");

	ws.on('message', function incoming(message) {
		
		// console.log('Server received get_tracklets from map');

		var client = new net.Socket();
		client.setTimeout(4000);
		client = client.setEncoding('utf8');
		client.connect(8766, '127.0.0.1', function() {
			// console.log('Connected to tracklets');
			// console.log("message");
			//console.log(message);
			client.write(message);
		});

		let chunks = []; // https://stackoverflow.com/a/45030133/8941739			
		client.on('data', function(data) {
			chunks.push(data); // https://stackoverflow.com/a/45030133/8941739
		}).on('end', function() {

			//console.log(chunks);
			if (chunks.length > 0) {
				let this_data = chunks.join("");
				var trackableObjectsArray = JSON.parse(this_data.replace(/'/g, '"'));

				if (typeof trackableObjectsArray !== 'undefined') {
					try {

						// console.log("-------------------------------------------------------");
						// console.log(JSON.stringify(trackableObjectsArray));
						// Send tracklets to browser
						ws.send(JSON.stringify(trackableObjectsArray));

					} catch(e) {
						console.log("error", e);
					}
				} else {
					// Send empty array to browser 
					ws.send(JSON.stringify([]));
				}
			} else {
				// Send empty array to browser
				ws.send(JSON.stringify([]));
			}
			
			client.destroy(); // kill client after server's response
		});

		client.on('error', function(ex) {
			console.log("Something happened trying to get trackelets from node ");
			client.destroy(); // kill client after error
			console.log(ex);
		});

		client.on('timeout', function() {
			console.log('tracklet socket timeout');
			client.destroy(); // have to .destroy() on timeout. If just .end(), it won't reconnect if user doesn't refresh browser
		});
		
	});
});


	
app.listen(port, () => console.log(`Example app listening on port ${port}!`))
