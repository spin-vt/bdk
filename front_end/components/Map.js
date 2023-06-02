import React, { useEffect, useRef } from "react";
import L from "leaflet";

function Map({ markers }) {
  const mapRef = useRef(null);
  const markersLayerRef = useRef(null);

  useEffect(() => {
    if (!mapRef.current) {
      // Initialize the map when the component mounts
      const map = L.map("map");
      L.tileLayer("http://{s}.tile.osm.org/{z}/{x}/{y}.png").addTo(map);
      map.setView([37.0902, -95.7129], 5); // Set view to United States coordinates
      mapRef.current = map;
    }

    const map = mapRef.current;

    // Cleanup the map when the component unmounts
    return () => {
      if (map) {
        map.remove();
        mapRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const myRenderer = L.canvas({ padding: 0.5 });

    if (!markersLayerRef.current) {
      // Initial rendering of markers
      const markerLayers = markers.map((marker, index) => {
        const color = marker.served ? "green" : "red"; // Determine marker color based on served property
        const markerLayer = L.circleMarker([marker.latitude, marker.longitude], {
          renderer: myRenderer,
          radius: 2, // Set a small radius value for each marker
          fillColor: color,
          color: color,
        }).bindPopup(`Marker ${index}`);
        return markerLayer;
      });

      const markersLayerGroup = L.layerGroup(markerLayers);
      markersLayerGroup.addTo(map);
      markersLayerRef.current = markersLayerGroup;
    } else {
      // Update marker colors
      const markersLayerGroup = markersLayerRef.current;
      map.removeLayer(markersLayerGroup); // Remove existing markers layer group
      const updatedMarkerLayers = markers.map((marker, index) => {
        const color = marker.served ? "green" : "red"; // Determine updated marker color based on served property
        const markerLayer = L.circleMarker([marker.latitude, marker.longitude], {
          renderer: myRenderer,
          radius: 2, // Set a small radius value for each marker
          fillColor: color,
          color: color,
        }).bindPopup(`Marker ${index}`);
        return markerLayer;
      });

      const updatedMarkersLayerGroup = L.layerGroup(updatedMarkerLayers);
      updatedMarkersLayerGroup.addTo(map);
      markersLayerRef.current = updatedMarkersLayerGroup;
    }
  }, [markers]);

  return <div id="map" style={{ height: "100vh" }}></div>;
}

export default Map;
