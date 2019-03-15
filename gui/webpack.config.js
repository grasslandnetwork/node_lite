
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

