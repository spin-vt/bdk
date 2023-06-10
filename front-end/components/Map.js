import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet.markercluster/dist/leaflet.markercluster";
import "../styles/Map.module.css";

function Map({ markers }) {
  const mapRef = useRef(null);
  const markersLayerRef = useRef(null);
  const [displayRedMarkers, setDisplayRedMarkers] = useState(true);
  const [displayGreenMarkers, setDisplayGreenMarkers] = useState(true);

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

    if (!markersLayerRef.current) {
      // Initial rendering of markers
      const markerLayers = markers.map((marker, index) => {
        const color = marker.served ? "green" : "red"; // Determine marker color based on served property
        const markerLayer = L.circleMarker([marker.latitude, marker.longitude], {
          radius: 2, // Set a small radius value for each marker
          fillColor: color,
          color: color,
        }).bindPopup(`Marker ${index}`);
        return markerLayer;
      });

      const markersLayerGroup = L.markerClusterGroup({
        iconCreateFunction: function (cluster) {
          const childCount = cluster.getChildCount();
          const zoomLevel = map.getZoom();
          const maxChildCount = 500000; // Maximum number of markers in a cluster
          const clusterColor = `hsl(200, 100%, ${100 - (childCount / maxChildCount) * 80}%)`; // Customize cluster color based on the number of markers and zoom level
          return L.divIcon({
            html: `<div style="background-color: ${clusterColor}">${childCount}</div>`,
            className: "marker-cluster",
            iconSize: L.point(40, 40),
          });
        },
      });

      markerLayers.forEach((markerLayer) => markersLayerGroup.addLayer(markerLayer));
      map.addLayer(markersLayerGroup);
      markersLayerRef.current = markersLayerGroup;
    } else {
      // Update marker colors
      const markersLayerGroup = markersLayerRef.current;
      markersLayerGroup.clearLayers(); // Remove existing markers from the layer group
      const updatedMarkerLayers = markers.map((marker, index) => {
        const color = marker.served ? "green" : "red"; // Determine updated marker color based on served property
        const markerLayer = L.circleMarker([marker.latitude, marker.longitude], {
          radius: 2, // Set a small radius value for each marker
          fillColor: color,
          color: color,
        }).bindPopup(`Marker ${index}`);
        return markerLayer;
      });

      updatedMarkerLayers.forEach((markerLayer) => {
        if (
          (displayRedMarkers && markerLayer.options.fillColor === "red") ||
          (displayGreenMarkers && markerLayer.options.fillColor === "green")
        ) {
          markersLayerGroup.addLayer(markerLayer);
        }
      });
    }
  }, [markers, displayRedMarkers, displayGreenMarkers]);

  const handleViewAllMarkers = () => {
    setDisplayRedMarkers(true);
    setDisplayGreenMarkers(true);
  };

  const handleViewRedMarkers = () => {
    setDisplayRedMarkers(true);
    setDisplayGreenMarkers(false);
  };

  const handleViewGreenMarkers = () => {
    setDisplayRedMarkers(false);
    setDisplayGreenMarkers(true);
  };

  return (
    <div>
      <div id="map" className="map-container" style={{ height: "100vh" }}></div>
      <div className="button-container">
        <button onClick={handleViewAllMarkers}>View All Markers</button>
        <button onClick={handleViewRedMarkers}>View Red Markers</button>
        <button onClick={handleViewGreenMarkers}>View Green Markers</button>
      </div>
    </div>
  );
}

export default Map;
