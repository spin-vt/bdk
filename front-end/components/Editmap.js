import React, { useEffect, useRef, useState, useContext } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import SelectedLocationContext from "../contexts/SelectedLocationContext";
import MapboxDraw from "@mapbox/mapbox-gl-draw";
import "@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css";
import * as turf from "@turf/turf";
import { styled } from "@mui/material/styles";
import "@maptiler/sdk/dist/maptiler-sdk.css";
import * as maptilersdk from "@maptiler/sdk";
import "maplibre-gl/dist/maplibre-gl.css";
import LayersIcon from "@mui/icons-material/Layers";
import { IconButton, Menu, MenuItem } from '@mui/material';
import SmallLoadingEffect from "./SmallLoadingEffect";
import { useRouter } from "next/router";
import Swal from 'sweetalert2';
import { backend_url } from "../utils/settings";
import SelectedPointsContext from "../contexts/SelectedPointsContext";
import MbtilesContext from "../contexts/MbtilesContext";

const StyledBaseMapIconButton = styled(IconButton)({
  width: "33px",
  height: "33px",
  top: "30%",
  position: "absolute",
  left: "10px",
  marginTop: '40px',
  zIndex: 1000,
  backgroundColor: "rgba(255, 255, 255, 1)",
  color: "#333",
  '&:hover': {
    backgroundColor: "rgba(255, 255, 255, 0.9)",
  },
  borderRadius: "4px",
  padding: "10px",
  boxShadow: "0px 1px 4px rgba(0, 0, 0, 0.3)",
});


function Editmap() {
  const mapContainer = useRef(null);
  const map = useRef(null);

  const [isLoadingForUntimedEffect, setIsLoadingForUntimedEffect] = useState(false);

  const allMarkersRef = useRef([]); // create a ref for allMarkers

  const selectedMarkersRef = useRef([]);
  const selectedSingleMarkersRef = useRef([]);

  const { selectedPoints, setSelectedPoints } = useContext(SelectedPointsContext);

  const { mbtid } = useContext(MbtilesContext);

  const router = useRouter();

  const currentPopup = useRef(null);

  const baseMaps = {
    STREETS:
      "https://api.maptiler.com/maps/streets/style.json?key=QE9g8fJij2HMMqWYaZlN",
    SATELLITE:
      "https://api.maptiler.com/maps/satellite/style.json?key=QE9g8fJij2HMMqWYaZlN",
    DARK: "https://api.maptiler.com/maps/backdrop-dark/style.json?key=QE9g8fJij2HMMqWYaZlN",
  };

  const [selectedBaseMap, setSelectedBaseMap] = useState("STREETS");

  const [basemapAnchorEl, setBasemapAnchorEl] = useState(null);

  const handleBasemapMenuOpen = (event) => {
    setBasemapAnchorEl(event.currentTarget);
  };

  const handleBasemapMenuClose = () => {
    setBasemapAnchorEl(null);
  };

  const handleBaseMapToggle = (baseMapName) => {
    console.log(baseMapName);
    setSelectedBaseMap(baseMapName);
    setBasemapAnchorEl(null);
  };

  const addSource = () => {
    const existingSource = map.current.getSource("custom");
    if (existingSource) {
      map.current.removeSource("custom");
    }

    console.log(mbtid);

    const user = localStorage.getItem("username");
    const tilesURL = mbtid
    ? `${backend_url}/tiles/${mbtid}/${user}/{z}/{x}/{y}.pbf`
    : `${backend_url}/tiles/${user}/{z}/{x}/{y}.pbf`;
    map.current.addSource("custom", {
      type: "vector",
      tiles: [tilesURL],
      maxzoom: 16,
    });
  };

  const addLayers = () => {
    let lineColor;
    let fillColor;

    switch (selectedBaseMap) {
      case "STREETS":
        lineColor = "#888";
        fillColor = "#42004F";
        break;
      case "SATELLITE":
        lineColor = "#FF00F7"; // Replace with appropriate color
        fillColor = "#565EC1"; // Replace with appropriate color
        break;
      case "DARK":
        lineColor = "#FF00F7"; // Replace with appropriate color
        fillColor = "#565EC1"; // Replace with appropriate color
        break;
      default:
        lineColor = "#888";
        fillColor = "#42004F";
    }

    map.current.addLayer({
      id: "custom-line",
      type: "line",
      source: "custom",
      layout: {
        "line-cap": "round",
        "line-join": "round",
      },
      paint: {
        "line-color": lineColor,
        "line-width": 2,
      },
      filter: ["==", ["get", "feature_type"], "LineString"], // Only apply this layer to linestrings
      "source-layer": "data",
    });

    map.current.addLayer({
      id: "custom-polygon",
      type: "fill",
      source: "custom",
      paint: {
        "fill-color": fillColor,
        "fill-opacity": 0.5,
      },
      filter: ["==", ["get", "feature_type"], "Polygon"], // Only apply this layer to polygons
      "source-layer": "data",
    });
    map.current.addLayer({
      id: "custom-point",
      type: "circle",
      source: "custom",
      paint: {
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["zoom"],
          5,
          0.5, // When zoom is less than or equal to 12, circle radius will be 1
          12,
          2,
          15,
          3, // When zoom is more than 12, circle radius will be 3
        ],
        "circle-color": [
          "case",
          ["==", ["feature-state", "served"], true], // change 'get' to 'feature-state'
          "#46DF39",
          "#FF0000",
        ],
      },
      filter: ["==", ["get", "feature_type"], "Point"], // Only apply this layer to points
      "source-layer": "data",
    });
  };

  const removeVectorTiles = () => {
    if (map.current.getLayer("custom-point")) {
      map.current.removeLayer("custom-point");
    }

    if (map.current.getLayer("custom-line")) {
      map.current.removeLayer("custom-line");
    }

    if (map.current.getLayer("custom-polygon")) {
      map.current.removeLayer("custom-polygon");
    }

    if (map.current.getSource("custom")) {
      map.current.removeSource("custom");
    }
  };

  const addVectorTiles = () => {
    removeVectorTiles();


    addSource();
    function handleSourcedata(e) {
      if (e.sourceId === "custom" && map.current.isSourceLoaded("custom")) {
        map.current.off("sourcedata", handleSourcedata);
        fetchMarkers().then(() => {
          addLayers();
        });
      }
    }
    map.current.on("sourcedata", handleSourcedata);

    map.current.on("draw.create", (event) => {
      const polygon = event.features[0];

      // Convert drawn polygon to turf polygon
      const turfPolygon = turf.polygon(polygon.geometry.coordinates);

      // Iterate over markers and select if they are inside the polygon
      const selected = allMarkersRef.current.filter((marker) => {
        const point = turf.point([marker.longitude, marker.latitude]);
        return turf.booleanPointInPolygon(point, turfPolygon);
      });

      changeToUnserved(selected);
      setSelectedPoints(selectedSingleMarkersRef.current);
    });

    map.current.on("click", "custom-point", function (e) {
      let featureProperties = e.features[0].properties;
      let featureId = e.features[0].id;  // Capture the feature ID here
      let featureCoordinates = e.features[0].geometry.coordinates;

      console.log(featureCoordinates);

      let content = "<h1>Marker Information</h1>";
      for (let property in featureProperties) {
        content += `<p><strong>${property}:</strong> ${featureProperties[property]}</p>`;
      }
      content += '<button id="setUnserved">Change to Unserve</button>';

      if (currentPopup.current) {
        currentPopup.current.remove();
        currentPopup.current = null;
      }


      const popup = new maplibregl.Popup({ closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(content)
        .addTo(map.current);

      document.getElementById('setUnserved').addEventListener('click', function () {
        // Logic to set the marker as unserved
        featureProperties.served = false;


        const currentFeatureState = map.current.getFeatureState({
          source: "custom",
          sourceLayer: "data",
          id: featureId,
        });

        if (currentFeatureState.hasOwnProperty("served")) {
          // Set the 'served' feature state to false
          map.current.setFeatureState(
            {
              source: "custom",
              sourceLayer: "data",
              id: featureId,
            },
            {
              served: false,
            }
          );

          const locationInfo = {
            id: featureId,
            latitude: featureCoordinates[1],
            longitude: featureCoordinates[0],
            address: featureProperties.address,
            served: false
          };
          selectedSingleMarkersRef.current.push(locationInfo);
          setSelectedPoints(selectedSingleMarkersRef.current);
        }

        // Refresh the popup content to reflect changes
        let updatedContent = "<h1>Marker Information</h1>";
        for (let property in featureProperties) {
          updatedContent += `<p><strong>${property}:</strong> ${featureProperties[property]}</p>`;
        }
        updatedContent += '<button id="setUnserved">Set to Unserve</button>';
        popup.setHTML(updatedContent);
      });

      currentPopup.current = popup;
    });

  };

  useEffect(() => {
    // Loop through the current ref list
    selectedSingleMarkersRef.current.forEach((marker) => {
      // Check if the marker is not in the selectedPoints
      if (!selectedPoints.some(point => point.id === marker.id)) {
        // If it's not in selectedPoints, set served back to true
        map.current.setFeatureState(
          {
            source: "custom",
            sourceLayer: "data",
            id: marker.id,
          },
          {
            served: true,
          }
        );
      }
    });

    // Sync ref with the current state
    selectedSingleMarkersRef.current = [...selectedPoints];

  }, [selectedPoints]); // Dependency on selectedPoints

  const changeToUnserved = (lastList) => {
    if (lastList !== undefined && lastList !== null) {
      lastList.forEach((marker) => {
        // Update the state of the selected markers
        marker.served = false;

        // Set the feature state for each updated marker
        if (map.current && map.current.getSource("custom")) {
          // Check if the marker's feature state has been previously set
          const currentFeatureState = map.current.getFeatureState({
            source: "custom",
            sourceLayer: "data",
            id: marker.id,
          });
          if (currentFeatureState.hasOwnProperty("served")) {
            // Set the 'served' feature state to false
            map.current.setFeatureState(
              {
                source: "custom",
                sourceLayer: "data",
                id: marker.id,
              },
              {
                served: false,
              }
            );
          }
        }
        selectedSingleMarkersRef.current.push(marker);
      });
    }
  };


  const setFeatureStateForMarkers = (markers) => {
    markers.forEach((marker) => {
      if (marker.served) {
        // This assumes that marker.id matches the feature id in your vector tile source
        map.current.setFeatureState(
          {
            source: "custom",
            sourceLayer: "data",
            id: marker.id,
          },
          {
            served: marker.served, // Use the served property from the marker data
          }
        );
      }
    });
  };

  const fetchMarkers = () => {
    if (
      allMarkersRef.current === undefined ||
      allMarkersRef.current === null ||
      allMarkersRef.current.length === 0
    ) {
      setIsLoadingForUntimedEffect(true);
      const url = mbtid 
    ? `${backend_url}/served-data/${mbtid}` 
    : `${backend_url}/served-data/None`;
    
      return fetch(url, {
        method: "GET",
        credentials: "include",
      })
        .then((response) => {
          if (response.status === 401) {
            Swal.fire({
              icon: "error",
              title: "Oops...",
              text: "Session expired, please log in again!",
            });
            // Redirect to login page
            router.push("/login");
            setIsLoading(false);
            return;
          }
          else if (response.status === 200) {
            return response.json();
          }
        })
        .then((data) => {
          const newMarkers = data.map((item) => ({
            address: item.address,
            id: item.location_id,
            latitude: item.latitude,
            longitude: item.longitude,
            served: item.served,
          }));

          setFeatureStateForMarkers(newMarkers);

          allMarkersRef.current = newMarkers; // Here's the state update
          setIsLoadingForUntimedEffect(false);
        })
        .catch((error) => {
          console.log(error);
          setIsLoadingForUntimedEffect(false);
        });
    } else {
      setFeatureStateForMarkers(allMarkersRef.current);
      return Promise.resolve(); // Returns a resolved Promise
    }
  };

  useEffect(() => {
    const initialStyle = baseMaps[selectedBaseMap];
    // Get current zoom level and center
    let currentZoom = 4;
    let currentCenter = [-98.35, 39.5];


    if (map.current) {
      currentZoom = map.current.getZoom();
      currentCenter = map.current.getCenter().toArray();
    }

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: initialStyle,
      center: currentCenter,
      zoom: currentZoom,
    });

    map.current.getCanvas().className = "mapboxgl-canvas maplibregl-canvas";
    map.current.getContainer().classList.add("mapboxgl-map");
    const canvasContainer = map.current.getCanvasContainer();
    canvasContainer.classList.add("mapboxgl-canvas-container");
    if (canvasContainer.classList.contains("maplibregl-interactive")) {
      canvasContainer.classList.add("mapboxgl-interactive");
    }

    const draw = new MapboxDraw({
      displayControlsDefault: false,
      controls: {
        polygon: true,
        trash: true,
      },
    });

    const originalOnAdd = draw.onAdd.bind(draw);
    draw.onAdd = (map) => {
      const controlContainer = originalOnAdd(map);
      controlContainer.classList.add(
        "maplibregl-ctrl",
        "maplibregl-ctrl-group",
      );
      return controlContainer;
    };

    //Remove the existing vector tile layer and source if they exist
    map.current.addControl(new maplibregl.NavigationControl(), "top-left");
    // map.current.addControl(new maplibregl.GeolocateControl(), "top-left");
    map.current.addControl(new maplibregl.ScaleControl(), "bottom-left");
    map.current.addControl(draw, "top-left");
    // When the base map changes, remove the existing vector tiles and add the new ones
    const handleBaseMapChange = () => {
      removeVectorTiles();
      addVectorTiles();
    };
    map.current.on("load", handleBaseMapChange);
  }, [selectedBaseMap, mbtid]);

  const { location } = useContext(SelectedLocationContext);
  const distinctMarkerRef = useRef(null);


  useEffect(() => {
    if (location && map.current) {
      const { latitude, longitude, zoomlevel } = location;

      if (distinctMarkerRef.current) {
        distinctMarkerRef.current.remove();
      }

      distinctMarkerRef.current = new maplibregl.Marker({
        color: "#FFFFFF",
        draggable: false,
      })
        .setLngLat([longitude, latitude])
        .addTo(map.current);

      map.current.flyTo({
        center: [longitude, latitude],
        zoom: zoomlevel,
      });
    } else {
      if (distinctMarkerRef.current) {
        distinctMarkerRef.current.remove();
        distinctMarkerRef.current = null;
      }
    }
  }, [location]);

  return (
    <div>
      <div>
        <StyledBaseMapIconButton onClick={handleBasemapMenuOpen}>
          <LayersIcon color="inherit" />
        </StyledBaseMapIconButton>
        <Menu
          id="basemap-menu"
          anchorEl={basemapAnchorEl}
          keepMounted
          open={Boolean(basemapAnchorEl)}
          onClose={handleBasemapMenuClose}
          anchorOrigin={{
            vertical: "top",
            horizontal: "right",
          }}
          transformOrigin={{
            vertical: "top",
            horizontal: "left",
          }}
        >
          {Object.keys(baseMaps).map((key) => (
            <MenuItem key={key} onClick={() => handleBaseMapToggle(key)}>
              {key}
            </MenuItem>
          ))}
        </Menu>
      </div>
      <div>
        {(isLoadingForUntimedEffect) && <SmallLoadingEffect isLoading={isLoadingForUntimedEffect} />}
      </div>

      <div ref={mapContainer} style={{ height: "100vh", width: "100%" }} />
    </div>
  );
}

export default Editmap;
