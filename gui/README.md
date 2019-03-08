
 Instructions
 
 You need to checkout the custom-layers branch in mapbox-gl-js (https://github.com/mapbox/mapbox-gl-js/tree/custom-layers)
 cd into it and do a dev-build (yarn run build-dev), and copy the newly created mapbox-gl-dev.js from its '/dist' directory to 'map/node_modules/mapbox-gl/dist' directory here and then add in the custom maxPitch (https://github.com/mapbox/mapbox-gl-js/issues/3731#issuecomment-409980664) set to 89.9 degrees before running the map.


This directory requires you to do
npm install
Followed by
MapboxAccessToken='your-Mapbox-token-here' npm run dev

You can get a free Mapbox Access token here -> https://docs.mapbox.com/help/glossary/access-token/
