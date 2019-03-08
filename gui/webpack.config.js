
// avoid destructuring for older Node version support
const path = require('path');
const resolve = require('path').resolve;
const webpack = require('webpack');
const outputDirectory = "dist";


// const HtmlWebpackPlugin = require('html-webpack-plugin');
// const CleanWebpackPlugin = require('clean-webpack-plugin');

const CONFIG = {
	mode: 'development',

	entry: {
		app: resolve('./app.js')
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
		open: true,
		proxy: {
			'/api': {
				target: 'ws://localhost:8080',
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

// This line enables bundling against src in this repo rather than installed module
module.exports = env => CONFIG;
