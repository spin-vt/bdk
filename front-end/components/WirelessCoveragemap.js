import React, { useEffect, useRef, useState, useContext } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { styled } from "@mui/material/styles";
import { backend_url } from "../utils/settings";


const WirelessCoveragemap = ({ imageUrl, bounds }) => {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);

  // Initialize the map
  useEffect(() => {
    mapRef.current = new maplibregl.Map({
      container: mapContainerRef.current,
      style: 'https://api.maptiler.com/maps/satellite/style.json?key=QE9g8fJij2HMMqWYaZlN',
      center: [(bounds.east + bounds.west) / 2, (bounds.north + bounds.south) / 2],
      zoom: 4, // Adjust the zoom level appropriately
    });

    return () => {
      mapRef.current.remove();
    };
  }, []); // Empty dependency array ensures this only runs once on mount

  // Update the image overlay when imageUrl or bounds change
  useEffect(() => {
    const map = mapRef.current;

    if (map && imageUrl && bounds) {
      // Ensure the bounds are numbers
      const westBound = parseFloat(bounds.west);
      const eastBound = parseFloat(bounds.east);
      const northBound = parseFloat(bounds.north);
      const southBound = parseFloat(bounds.south);

      map.once('load', () => {
        // First remove the existing image source and layer if they exist
        if (map.getSource('image-overlay')) {
          map.removeLayer('overlay');
          map.removeSource('image-overlay');
        }

        // Add new image source
        map.addSource('image-overlay', {
          type: 'image',
          url: imageUrl,
          coordinates: [
            [westBound, northBound], // top left
            [eastBound, northBound], // top right
            [eastBound, southBound], // bottom right
            [westBound, southBound], // bottom left
          ],
        });

        // Add new image layer
        map.addLayer({
          id: 'overlay',
          source: 'image-overlay',
          type: 'raster',
          paint: {
            'raster-opacity': 0.85,
            'raster-fade-duration': 0,
          },
        });
      });

      const longitude = (westBound + eastBound) / 2;
      const latitude = (northBound + southBound) / 2;
      mapRef.current.flyTo({
        center: [longitude, latitude],
        zoom: 8,
      });

      // If the map was already loaded, we need to manually trigger the update
      if (map.isStyleLoaded()) {
        map.fire('load');
      }
    }
  }, [imageUrl, bounds]); // This will run every time imageUrl or bounds change

  return <div ref={mapContainerRef} style={{ height: '600px', width: '100%' }} />
};

export default WirelessCoveragemap;