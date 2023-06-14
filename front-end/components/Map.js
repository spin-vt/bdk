import React, { useEffect, useRef, useState, useContext } from "react";
import L from "leaflet";
import "leaflet.markercluster/dist/leaflet.markercluster";
import "../styles/Map.module.css";
import Papa from "papaparse";
import SelectedLocationContext from "./SelectedLocationContext";

const h3 = require("h3-js");

function Map() {
  const mapRef = useRef(null);
  const [hexIndexToMarkers, setHexIndexToMarkers] = useState({});
  const polygonsRef = useRef([]);
  const markerLayersRef = useRef([]);
  const [markers, setMarkers] = useState([]);

  const { location } = useContext(SelectedLocationContext);

  // useEffect(() => {
  //   Papa.parse("/fabric.csv", {
  //     download: true,
  //     header: true,
  //     complete: function (results) {
  //       const markers = results.data.map((marker) => ({
  //         latitude: parseFloat(marker.latitude),
  //         longitude: parseFloat(marker.longitude),
  //       }));
  //       setMarkers(markers);
  //     },
  //   });
  // }, []);

  useEffect(() => {
    // Initialize map on component mount
    const map = L.map("map");
    L.tileLayer("http://{s}.tile.osm.org/{z}/{x}/{y}.png").addTo(map);
    map.setView([37.0902, -95.7129], 5); // Set view to United States coordinates
    mapRef.current = map;

    // Cleanup on component unmount
    return () => {
      if (map) {
        map.remove();
        mapRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    let newHexIndexToMarkers = {};

    markers.forEach((marker) => {
      const h3Index = h3.latLngToCell(marker.latitude, marker.longitude, 7);

      // Add marker to hex index mapping
      if (!newHexIndexToMarkers[h3Index]) {
        newHexIndexToMarkers[h3Index] = [];
      }
      newHexIndexToMarkers[h3Index].push(marker);
    });

    setHexIndexToMarkers(newHexIndexToMarkers);
  }, [markers]);

  useEffect(() => {
    const map = mapRef.current;

    Object.keys(hexIndexToMarkers).forEach((h3Index) => {
      const hexBoundary = h3.cellToBoundary(h3Index);
      const latLngs = hexBoundary.map((coord) => L.latLng(coord[0], coord[1]));

      const polygon = L.polygon(latLngs, {
        color: "blue",
        fillColor: "blue",
        fillOpacity: 0.5,
      }).addTo(map);

      polygonsRef.current.push(polygon);

      polygon.on("click", () => {
        const currentZoom = map.getZoom();
        if (currentZoom >= 10) {
          hexIndexToMarkers[h3Index].forEach((marker) => {
            let markerLayer;
            if (marker.served === true) {
              markerLayer = L.circleMarker(
                [marker.latitude, marker.longitude],
                {
                  radius: 5,
                  color: "green",
                  fillColor: "green",
                  fillOpacity: 1,
                }
              ).addTo(map);
            } else {
              markerLayer = L.circleMarker(
                [marker.latitude, marker.longitude],
                {
                  radius: 5,
                  color: "red",
                  fillColor: "red",
                  fillOpacity: 1,
                }
              ).addTo(map);
            }
            markerLayersRef.current.push(markerLayer);
          });
          polygon.setStyle({ fillOpacity: 0 });
        }
      });
    });

    map.on("zoomend", () => {
      const currentZoom = map.getZoom();
      if (currentZoom < 10) {
        polygonsRef.current.forEach((polygon) => {
          polygon.setStyle({ fillOpacity: 0.5 });
        });

        markerLayersRef.current.forEach((markerLayer) => {
          map.removeLayer(markerLayer);
        });
        markerLayersRef.current = [];
      }
    });
  }, [hexIndexToMarkers]);

  useEffect(() => {
    console.log(location);
    if (location && mapRef.current) {
      const { latitude, longitude } = location;
      mapRef.current.setView([latitude, longitude], 13);
    }
  }, [location]);

  return (
    <div>
      <div id="map" className="map-container" style={{ height: "100vh" }}></div>
    </div>
  );
}

export default Map;
