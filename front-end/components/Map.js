import React, { useEffect, useRef, useState, useContext } from "react";
import L from "leaflet";
import "leaflet.markercluster/dist/leaflet.markercluster";
import "../styles/Map.module.css";
import SelectedLocationContext from "./SelectedLocationContext";
import { Toolbar, Switch, FormControlLabel } from '@material-ui/core';
import { makeStyles } from '@material-ui/core/styles';
import KeyboardDoubleArrowUpIcon from '@mui/icons-material/KeyboardDoubleArrowUp';

const useStyles = makeStyles({
  expandToolbarButton: {
    top: '20px',
    position: 'absolute',  // adjust as needed
    minHeight: '6vh',
    left: '50%',  // center the Toolbar
    transform: "translateX(-50%)",
    zIndex: 1000,
    backgroundColor: '#0691DA',
    border: '0px',
    color: '#fff', // white text
    '&:hover': {
      backgroundColor: '#73A5C6',
    },
    borderRadius: '30px',
    paddingLeft: '20px',
    paddingRight: '20px',

  },
  collapseToolbarContainer: {
    display: 'flex',
    alignItems: 'center', // this will align items vertically in the center
    justifyContent: 'center',
    top: '85px',
    position: 'absolute',  // adjust as needed
    minHeight: '3vh',
    maxWidth: '8vw',
    left: '50%',  // center the Toolbar
    transform: "translateX(-50%)",
    zIndex: 1000,
    backgroundColor: '#3A7BD5', // Material-UI secondary color
    color: '#fff', // white text
    '&:hover': {
      backgroundColor: '#73A5C6', // darker shade for hover state
    },
    border: '0px',
    borderRadius: '10px',
    paddingLeft: '10px',
    paddingRight: '10px',
  },
  toolbar: {
    position: 'absolute',  // adjust as needed
    maxHeight: '5vh',
    left: '50%',  // center the Toolbar
    transform: "translateX(-50%)",
    width: "50vw",
    borderRadius: '50px',
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
    zIndex: 1000,
    top: '20px',
    justifyContent: 'center',

  }
});


const h3 = require("h3-js");

function Map({ markers }) {

  const classes = useStyles();
  const mapRef = useRef(null);
  const [hexIndexToMarkers, setHexIndexToMarkers] = useState({});
  const polygonsRef = useRef([]);
  const markerLayersRef = useRef([]);

  const [showServed, setShowServed] = useState(true);
  const [showUnserved, setShowUnserved] = useState(true);

  const [isToolbarExpanded, setIsToolbarExpanded] = useState(false);
  const [showExpandButton, setShowExpandButton] = useState(true);

  const handleServedChange = (event) => {
    setShowServed(event.target.checked);
  }

  const handleUnservedChange = (event) => {
    setShowUnserved(event.target.checked);
  }

  const { location } = useContext(SelectedLocationContext);
  const distinctMarkerRef = useRef(null);
  const [computing, setComputing] = useState(false);

  const clearMapLayers = () => {
    if (mapRef.current) {
      polygonsRef.current.forEach((polygon) => {
        mapRef.current.removeLayer(polygon);
      });
      polygonsRef.current = [];

      markerLayersRef.current.forEach((markerLayer) => {
        mapRef.current.removeLayer(markerLayer);
      });
      markerLayersRef.current = [];
    }
  };

  useEffect(() => {
    const map = L.map("map");
    L.tileLayer("http://{s}.tile.osm.org/{z}/{x}/{y}.png").addTo(map);
    map.setView([37.0902, -95.7129], 5);
    mapRef.current = map;



    map.on('zoomend', () => {
      const zoom = map.getZoom();
      if (zoom < 10) {
        if (distinctMarkerRef.current) {
          mapRef.current.removeLayer(distinctMarkerRef.current);
          distinctMarkerRef.current = null;
        }

        polygonsRef.current.forEach((polygon) => {
          const h3Index = polygon.options.h3Index;
          const containsServed = hexIndexToMarkers[h3Index].some(marker => marker.served);
          const containsUnserved = hexIndexToMarkers[h3Index].some(marker => !marker.served);
          if (containsUnserved && !showUnserved) {
            if (!containsServed) {
              polygon.setStyle({ fillOpacity: 0, fillColor: "transparent", color: "transparent" });
            }
            else {
              if (!showServed) {
                polygon.setStyle({ fillOpacity: 0, fillColor: "transparent", color: "transparent" });
              }
              else {
                polygon.setStyle({ fillOpacity: 0.5, fillColor: "green", color: "green" });
              }
            }
          }
          else if (containsServed && !showServed) {
            if (!containsUnserved) {
              polygon.setStyle({ fillOpacity: 0, fillColor: "transparent", color: "transparent" });
            }
            else {
              if (!showUnserved) {
                polygon.setStyle({ fillOpacity: 0, fillColor: "transparent", color: "transparent" });
              }
              else {
                polygon.setStyle({ fillOpacity: 0.5, fillColor: "red", color: "red" });
              }
            }
          }
          else {
            let color = 'blue';  // default color when polygon contains both served and unserved
            if (containsServed && !containsUnserved) {
              color = 'green';  // only contains served points
            } else if (containsUnserved && !containsServed) {
              color = 'red';  // only contains unserved points
            }

            polygon.setStyle({ fillOpacity: 0.5, fillColor: color, color: color });
          }

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
  }, [hexIndexToMarkers, showServed, showUnserved]);

  useEffect(() => {
    clearMapLayers();

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

    clearMapLayers();

    Object.keys(hexIndexToMarkers).forEach((h3Index) => {
      const hexBoundary = h3.cellToBoundary(h3Index);
      const latLngs = hexBoundary.map((coord) => L.latLng(coord[0], coord[1]));

      const containsServed = hexIndexToMarkers[h3Index].some(marker => marker.served);
      const containsUnserved = hexIndexToMarkers[h3Index].some(marker => !marker.served);

      let color = 'blue';  // default color when polygon contains both served and unserved
      if (containsServed && !containsUnserved) {
        color = 'green';  // only contains served points
      } else if (containsUnserved && !containsServed) {
        color = 'red';  // only contains unserved points
      }
      const polygon = L.polygon(latLngs, {
        color: color,
        fillColor: color,
        fillOpacity: 0.5,
        h3Index,
      }).addTo(map);

      polygonsRef.current.push(polygon);

      polygon.on("click", () => {
        const currentZoom = map.getZoom();
        if (currentZoom >= 10) {
          hexIndexToMarkers[h3Index].forEach((marker) => {
            let markerLayer;

            let color;
            if (marker.type === "lte") {
              color = "purple";
            } else if (marker.type === "non-lte") {
              color = "yellow";
            } else if (marker.served === true) {
              color = 'green';
              if (!showServed) return;
            } else {
              color = 'red';
              if (!showUnserved) return;
            }

            markerLayer = L.circleMarker([marker.latitude, marker.longitude], {
              radius: 5,
              color: color,
              fillColor: color,
              fillOpacity: 1,
            }).addTo(map);

            markerLayer.bindPopup(`
              <strong>Name:</strong> ${marker.name} <br/>
              <strong>ID:</strong> ${marker.id} <br/>
              <strong>Download Speed:</strong> ${marker.download_speed} <br/>
              <strong>Upload Speed:</strong> ${marker.upload_speed} <br/>
              <strong>Technology:</strong> ${marker.technology} <br/>
              <strong>Latitude:</strong> ${marker.latitude} <br/>
              <strong>Longitude:</strong> ${marker.longitude} <br/>
              <strong>Served:</strong> ${marker.served ? "Yes" : "No"} <br/>
              <strong>Type:</strong> ${marker.type}
            `);

            polygon.setStyle({ fillOpacity: 0, fillColor: "transparent", color: color });
            markerLayersRef.current.push(markerLayer);
          });
        }
      });
    });
  }, [hexIndexToMarkers, showServed, showUnserved]);

  useEffect(() => {
    polygonsRef.current.forEach((polygon) => {
      const h3Index = polygon.options.h3Index;
      const containsServed = hexIndexToMarkers[h3Index].some(marker => marker.served);
      const containsUnserved = hexIndexToMarkers[h3Index].some(marker => !marker.served);

      if (containsUnserved && !showUnserved) {
        if (!containsServed) {
          polygon.setStyle({ fillOpacity: 0, fillColor: "transparent", color: "transparent" });
        }
        else {
          if (!showServed) {
            polygon.setStyle({ fillOpacity: 0, fillColor: "transparent", color: "transparent" });
          }
          else {
            polygon.setStyle({ fillOpacity: 0.5, fillColor: "green", color: "green" });
          }
        }
      }
      else if (containsServed && !showServed) {
        if (!containsUnserved) {
          polygon.setStyle({ fillOpacity: 0, fillColor: "transparent", color: "transparent" });
        }
        else {
          if (!showUnserved) {
            polygon.setStyle({ fillOpacity: 0, fillColor: "transparent", color: "transparent" });
          }
          else {
            polygon.setStyle({ fillOpacity: 0.5, fillColor: "red", color: "red" });
          }
        }
      }
      else {
        let color = 'blue';  // default color when polygon contains both served and unserved
        if (containsServed && !containsUnserved) {
          color = 'green';  // only contains served points
        } else if (containsUnserved && !containsServed) {
          color = 'red';  // only contains unserved points
        }

        polygon.setStyle({ fillOpacity: 0.5, fillColor: color, color: color });
      }
    });
  }, [showServed, showUnserved, hexIndexToMarkers]);

  useEffect(() => {
    console.log(location);
    if (location && mapRef.current) {
      const { latitude, longitude } = location;

      if (distinctMarkerRef.current) {
        mapRef.current.removeLayer(distinctMarkerRef.current);
      }

      const myIcon = L.icon({
        iconUrl: "/map_marker.svg",
        iconSize: [38, 95],
        iconAnchor: [19, 95],
        popupAnchor: [-3, -76],
      });
      distinctMarkerRef.current = L.marker([latitude, longitude], {
        icon: myIcon,
      }).addTo(mapRef.current);

      const h3Index = h3.latLngToCell(latitude, longitude, 7);
      mapRef.current.setView([latitude, longitude], 20);

      polygonsRef.current.forEach((polygon) => {
        if (polygon.options.h3Index === h3Index) {
          polygon.setStyle({ fillOpacity: 0, fillColor: "transparent", color: "transparent" });
          hexIndexToMarkers[h3Index].forEach((marker) => {
            let markerLayer;
            if (marker.served === true) {
              markerLayer = L.circleMarker([marker.latitude, marker.longitude], {
                radius: 5,
                color: "green",
                fillColor: "green",
                fillOpacity: 1,
              }).addTo(mapRef.current);
            } else {
              markerLayer = L.circleMarker([marker.latitude, marker.longitude], {
                radius: 5,
                color: "red",
                fillColor: "red",
                fillOpacity: 1,
              }).addTo(mapRef.current);
            }
            markerLayer.bindPopup(`
              <strong>Name:</strong> ${marker.name} <br/>
              <strong>ID:</strong> ${marker.id} <br/>
              <strong>Download Speed:</strong> ${marker.download_speed} <br/>
              <strong>Upload Speed:</strong> ${marker.upload_speed} <br/>
              <strong>Technology:</strong> ${marker.technology} <br/>
              <strong>Latitude:</strong> ${marker.latitude} <br/>
              <strong>Longitude:</strong> ${marker.longitude} <br/>
              <strong>Served:</strong> ${marker.served ? "Yes" : "No"} <br/>
              <strong>Type:</strong> ${marker.type}
            `);

            markerLayersRef.current.push(markerLayer);
          });
        }
      });
    }
    else {
      if (distinctMarkerRef.current) {
        mapRef.current.removeLayer(distinctMarkerRef.current);
        distinctMarkerRef.current = null;
      }
    }
  }, [location]);


  return (
    <div>
      <div className={classes.toolbarContainer}>
        {showExpandButton && (
          <button className={classes.expandToolbarButton} onClick={() => { setIsToolbarExpanded(true); setShowExpandButton(false); }}>
            Show Toolbar
          </button>
        )}
        {isToolbarExpanded && (
          <div >
            <Toolbar className={classes.toolbar}>
              <FormControlLabel
                control={<Switch checked={showServed} onChange={handleServedChange} />}
                label="Show Served"
                id="served-toggle"
              />
              <FormControlLabel
                control={<Switch checked={showUnserved} onChange={handleUnservedChange} />}
                label="Show Unserved"
                id="unserved-toggle"
              />

            </Toolbar>

            <button className={classes.collapseToolbarContainer} onClick={() => { setIsToolbarExpanded(false); setShowExpandButton(true); }}>
              <KeyboardDoubleArrowUpIcon />
              Collapse
            </button>
          </div>
        )}
      </div>
      <div>
        <div id="map" className="map-container" style={{ height: "100vh" }}></div>
      </div>
    </div>
  );
}

export default Map;
