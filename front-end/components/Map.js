import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet.markercluster/dist/leaflet.markercluster";
import "../styles/Map.module.css";
import destination from "@turf/destination";
import { point } from "@turf/helpers";
import hexGrid from "@turf/hex-grid";

function calculateCenter(latMin, latMax, lonMin, lonMax) {
  return [(latMin + latMax) / 2, (lonMin + lonMax) / 2];
}

function calculateRadius(latMin, latMax, lonMin, lonMax) {
  return Math.min(Math.abs(latMax - latMin), Math.abs(lonMax - lonMin)) / 2;
}

// function rotatePoint(point, center, angle) {
//   const radians = (Math.PI / 180) * angle;
//   const cos = Math.cos(radians);
//   const sin = Math.sin(radians);
//   const nx = (cos * (point[0] - center[0])) + (sin * (point[1] - center[1])) + center[0];
//   const ny = (cos * (point[1] - center[1])) - (sin * (point[0] - center[0])) + center[1];
//   return [nx, ny];
// }



function Map({ markers }) {
  const mapRef = useRef(null);
  const markersLayerRef = useRef(null);
  const [displayRedMarkers, setDisplayRedMarkers] = useState(true);
  const [displayGreenMarkers, setDisplayGreenMarkers] = useState(true);
  const hexagonLayerRef = useRef(null);
  const [bbox, setBBox] = useState([]);
  const [isFetching, setIsFetching] = useState(true);
  const [zoom, setZoom] = useState(5);

  function getHexagonPoints(center, radius, rotation) {
    const points = [];
    for (let i = 0; i < 6; i++) {
      const degrees = 60 * i - 30;
      const bearing = (degrees + rotation + 360) % 360;
      const destinationPoint = destination(point(center), radius, bearing, {
        units: "degrees",
      });
      points.push(destinationPoint.geometry.coordinates);
    }
    points.push(points[0]);
    return [points];
  }
  
  function fetchHexGridPoints(filename) {
    setIsFetching(true);
    const data = {
      filename: `${filename}`,
    };
  
    fetch("http://localhost:8000/api/coordinates", {
      method: "POST", // or 'PUT'
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log(data);
        // The data here is the response from flask API
        // Now pass these values to Map component
        if (mapRef.current) {
          setBBox(data);
        }
        setIsFetching(false);
      })
      .catch((error) => {
        console.error("Error:", error);
        setBBox(null);
        setIsFetching(false);
      });
      
  }

  useEffect(() => {
    // call the fetch function
    fetchHexGridPoints("fabric.csv");
  }, []);

  useEffect(() => {
    
    if (!mapRef.current) {
      // Initialize the map when the component mounts
      const map = L.map("map");
      L.tileLayer("http://{s}.tile.osm.org/{z}/{x}/{y}.png").addTo(map);
      map.setView([37.0902, -95.7129], 5); // Set view to United States coordinates
      mapRef.current = map;

      /* Drawing single hexagon*/
      // let latMin = 35;
      // let latMax = 39;
      // let lonMin = -106;
      // let lonMax = -101;

      // // Calculate the center point
      // let center = calculateCenter(latMin, latMax, lonMin, lonMax);

      // // Calculate the radius (half of the shorter side of the rectangle)
      // let radius = Math.min(Math.abs(latMax - latMin), Math.abs(lonMax - lonMin)) / 2;

      // // console.log(getHexagonPoints(center, radius, 90));
      // // Create hexagon and add it to the map
      // const hexagon = L.polygon(getHexagonPoints(center, radius, 60), {color: 'blue'}).addTo(map);
      // hexagonLayerRef.current = hexagon;
    }
    else {
      mapRef.current.on("zoomend", function () {
        const currentZoom = mapRef.current.getZoom();
        setZoom(currentZoom);
      });
    }

    const map = mapRef.current;

    // Define bounding box and cell side
    // const bbox = fetchHexGridPoints("fabric.csv");
    // console.log(bbox);
    if (bbox && !isFetching) {
      
      const options = { units: "degrees" };

      bbox.forEach((box) => {
        const cellSide = Math.min(
          Math.abs(box.latitude.max - box.latitude.min),
          Math.abs(box.longitude.max - box.longitude.min)
        ); 
        // The -1, +1 is so that the resulting hexagon is visible, we should fine-grained the dataset such that 
        // we can use the actual resulting data to plot hex-grids
        const bboxSingle = [box.longitude.min - 1, box.latitude.min - 1, box.longitude.max + 1, box.latitude.max + 1];
        const hexGridGeoJSON = hexGrid(bboxSingle, cellSide, options);
  
        // Add each hexagon to the map
        hexGridGeoJSON.features.forEach((hex) => {
          const hexLayer = L.geoJSON(hex, { color: "#ABABAB" });
          hexLayer.addTo(map);
        });
      });
    }

    // Cleanup the map when the component unmounts
    return () => {
      if (map) {
        map.remove();
        mapRef.current = null;
      }
      if (mapRef.current) {
        mapRef.current.off("zoomed");
      }
    };
  }, [bbox, isFetching]);



  useEffect(() => {
    const map = mapRef.current;

    if (!markersLayerRef.current) {
      // Initial rendering of markers
      const markerLayers = markers.map((marker, index) => {
        const color = marker.served ? "green" : "red"; // Determine marker color based on served property
        const markerLayer = L.circleMarker(
          [marker.latitude, marker.longitude],
          {
            radius: 2, // Set a small radius value for each marker
            fillColor: color,
            color: color,
          }
        ).bindPopup(`Marker ${index}`);
        return markerLayer;
      });

      const markersLayerGroup = L.markerClusterGroup({
        iconCreateFunction: function (cluster) {
          const childCount = cluster.getChildCount();
          const zoomLevel = map.getZoom();
          const maxChildCount = 500000; // Maximum number of markers in a cluster
          const clusterColor = `hsl(200, 100%, ${
            100 - (childCount / maxChildCount) * 80
          }%)`; // Customize cluster color based on the number of markers and zoom level
          return L.divIcon({
            html: `<div style="background-color: ${clusterColor}">${childCount}</div>`,
            className: "marker-cluster",
            iconSize: L.point(40, 40),
          });
        },
      });

      markerLayers.forEach((markerLayer) =>
        markersLayerGroup.addLayer(markerLayer)
      );
      map.addLayer(markersLayerGroup);
      markersLayerRef.current = markersLayerGroup;
    } else {
      // Update marker colors
      const markersLayerGroup = markersLayerRef.current;
      markersLayerGroup.clearLayers(); // Remove existing markers from the layer group
      const updatedMarkerLayers = markers.map((marker, index) => {
        const color = marker.served ? "green" : "red"; // Determine updated marker color based on served property
        const markerLayer = L.circleMarker(
          [marker.latitude, marker.longitude],
          {
            radius: 2, // Set a small radius value for each marker
            fillColor: color,
            color: color,
          }
        ).bindPopup(`Marker ${index}`);
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
