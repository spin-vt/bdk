import React, { useEffect, useRef, useState, useContext } from "react";
import L from "leaflet";
import "leaflet.markercluster/dist/leaflet.markercluster";
import "../styles/Map.module.css";
import SelectedLocationContext from "./SelectedLocationContext";

const h3 = require("h3-js");

function Map({markers}) {
  const mapRef = useRef(null);
  const [hexIndexToMarkers, setHexIndexToMarkers] = useState({});
  const polygonsRef = useRef([]);
  const markerLayersRef = useRef([]);

  const { location } = useContext(SelectedLocationContext);

  useEffect(() => {
    const map = L.map("map");
    L.tileLayer("http://{s}.tile.osm.org/{z}/{x}/{y}.png").addTo(map);
    map.setView([37.0902, -95.7129], 5);
    mapRef.current = map;

    map.on('zoomend', () => {
      const zoom = map.getZoom();
      if (zoom < 10) {
        polygonsRef.current.forEach((polygon) => {
          polygon.setStyle({
            fillOpacity: 0.5,
            fillColor: "blue",
            color: "blue",
          });
        });

        markerLayersRef.current.forEach((markerLayer) => {
          map.removeLayer(markerLayer);
        });
        markerLayersRef.current = [];
      }
    });

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
        h3Index,
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
          polygon.setStyle({ fillOpacity: 0, fillColor: "transparent", color: "transparent"});
        }
      });
    });
  }, [hexIndexToMarkers]);

  useEffect(() => {
    console.log(location);
    if (location && mapRef.current) {
      const { latitude, longitude } = location;
      const h3Index = h3.latLngToCell(latitude, longitude, 7);
      mapRef.current.setView([latitude, longitude], 13);

      polygonsRef.current.forEach((polygon) => {
        if (polygon.options.h3Index === h3Index) {
          polygon.setStyle({ fillOpacity: 0, fillColor: "transparent", color: "transparent"});
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
              ).addTo(mapRef.current);
            } else {
              markerLayer = L.circleMarker(
                [marker.latitude, marker.longitude],
                {
                  radius: 5,
                  color: "red",
                  fillColor: "red",
                  fillOpacity: 1,
                }
              ).addTo(mapRef.current);
            }
            markerLayersRef.current.push(markerLayer);
          });
        }
      });
    }
  }, [location]);

  return (
    <div>
      <div id="map" className="map-container" style={{ height: "100vh" }}></div>
    </div>
  );
}

export default Map;
