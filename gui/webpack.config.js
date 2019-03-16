
// avoid destructuring for older Node version support
const path = require('path');
const resolve = require('path').resolve;
const webpack = require('webpack');
const outputDirectory = "dist";


// const HtmlWebpackPlugin = require('html-webpack-plugin');
// const CleanWebpackPlugin = require('clean-webpack-plugin');

module.exports = env => {

	var CONFIG = {
		mode: 'development',

		entry: {
			app: resolve('./app.js')
		},

		resolve: {
			alias: {
				  // From mapbox-gl-js README. Required for non-browserify bundlers (e.g. webpack) if you want to use your own modified mapbox-gl.js (https://github.com/uber/deck.gl/blob/b775505a04fe45504e787c99beb5e3d31f95a3fd/test/apps/mapbox-layers/webpack.config.js#L17):
				  // I needed an 89.9 degree max pitch....
				  // So following these instructions (https://github.com/uber/deck.gl/blob/b775505a04fe45504e787c99beb5e3d31f95a3fd/test/apps/mapbox-layers/README.md) with regard to the custom-layers branch (https://github.com/mapbox/mapbox-gl-js/tree/custom-layers) ...
				  // I downloaded version 48.0. cd into it and did a dev-build (yarn run build-dev), and copy the newly created mapbox-gl-dev.js from its '/dist' directory to 'map/node_modules/mapbox-gl/dist' directory here ...
				  // ... I took version 48.0 in accordance with this user's patch (https://github.com/mapbox/mapbox-gl-js/issues/3731#issuecomment-409980664) and then set the custom maxPitch to 89.9 degrees and stored it here as mapbox-gl-dev.js
		
				  'mapbox-gl$': resolve('./src/client/mapbox-gl-dev.js')
			  }
		},

		devtool: 'inline-source-map',
		

		output: {
			library: 'App'
		},


		module: {
			rules: [
				{
					// Compile ES2015 using buble
					test: /\.js$/,
					loader: 'buble-loader',
					include: [resolve('.')],
					exclude: [/node_modules/],
					options: {
						objectAssign: 'Object.assign'
					}
				}
			]
		},

		// Optional: Enables reading mapbox token from environment variable
		plugins: [new webpack.EnvironmentPlugin(['MapboxAccessToken'])],
		
		devServer: {
			port: 3000,
			host: env.HOST,
			open: true,
			proxy: {
				'/api': {
					target: 'ws://'+env.HOST+':8080',
					ws: true
				},
			},

		},

		// plugins: [
		// 	new CleanWebpackPlugin([outputDirectory]),
		// 	new HtmlWebpackPlugin({
		// 		template: "./index.html"
		// 	})
		// ]
	};

	return CONFIG;
};

