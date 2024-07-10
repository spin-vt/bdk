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
import SelectedPolygonContext from "../contexts/SelectedPolygonContext";
import SelectedPolygonAreaContext from "../contexts/SelectedPolygonAreaContext.js";
import { useFolder } from "../contexts/FolderContext.js";
import { Typography, Checkbox, Box, Paper, Button } from '@mui/material';


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

  const selectedPolygonsRef = useRef([]);

  const { selectedPolygons, setSelectedPolygons } = useContext(SelectedPolygonContext);
  const { selectedPolygonsArea, setSelectedPolygonsArea } = useContext(SelectedPolygonAreaContext);

  const { folderID, setFolderID } = useFolder();
  const colors = ["#a6cee3", "#1f78b4", "#fdbf6f", "#ff7f00", "#cab2d6", "#6a3d9a", "#ffff99", "#b15928"];

  const colorRed = "#FF0000";
  const colorGreen = "#46DF39";

  const [combinationToColorMap, setCombinationToColorMap] = useState({});
  const [combinationToPoints, setCombinationToPoints] = useState({});


  const [selectedPoints, setSelectedPoints] = useState([]);
  const [selectedPolygonFeature, setSelectedPolygonFeature] = useState(null);

  var colorsArrayIndex = 0;

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


    const tilesURL = `${backend_url}/api/tiles/${folderID}/{z}/{x}/{y}.pbf`
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
      filter: [
        "all",
        ["any", // Use the "any" logical operator
          ["==", ["get", "feature_type"], "Polygon"],
          ["==", ["get", "feature_type"], "MultiPolygon"]
        ],
      ],
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
          // Check if a color is set in the feature-state, if so use it
          ["to-boolean", ["feature-state", "color"]], // Ensure color is treated as a boolean (true if exists)
          ["feature-state", "color"],  // Use the color from feature state
          // If no color is set in the feature-state, default to red
          colorRed
        ]
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


  const initializeCombinationToColorMap = (selected) => {

    
    let combinationToColorMap = {};
    let combinationToPoints = {};
    if (selected === undefined || selected.length === 0) {
      return { combinationToColorMap, combinationToPoints };
    }

    const allCoverages = new Set();
    selected.forEach(marker => {
      marker.coveredBy.forEach(file => allCoverages.add(file));
    });

    const fullCoverageKey = Array.from(allCoverages).sort().join(", ");
    combinationToColorMap[fullCoverageKey] = colorRed; // Red for full coverage

    selected.forEach(marker => {
      const markerCoverageKey = Array.from(marker.coveredBy).sort().join(", ");
      if (!combinationToColorMap.hasOwnProperty(markerCoverageKey)) {
        combinationToColorMap[markerCoverageKey] = colors[colorsArrayIndex % colors.length];
        colorsArrayIndex++;
      }
      if (!combinationToPoints[markerCoverageKey]) {
        combinationToPoints[markerCoverageKey] = [];
      }
      combinationToPoints[markerCoverageKey].push(marker);
    });

    return { combinationToColorMap, combinationToPoints };
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

      // Iterate over markers and select if they are inside the polygon and served is true
      let selected = allMarkersRef.current.filter((marker) => {
        const point = turf.point([marker.longitude, marker.latitude]);
        const isInsidePolygon = turf.booleanPointInPolygon(point, turfPolygon);
        return isInsidePolygon && marker.served;
      });


      // Assign colors to markers based on their coverage combination


      const { combinationToColorMap, combinationToPoints } = initializeCombinationToColorMap(selected);
      setSelectedPoints(selected);
      setSelectedPolygonFeature(polygon);
      setCombinationToColorMap(combinationToColorMap);
      setCombinationToPoints(combinationToPoints);

      selected.forEach(marker => {
        const markerCoverageKey = Array.from(marker.coveredBy).sort().join(", ");
        const markercolor = combinationToColorMap[markerCoverageKey];

        marker.served = false;
        marker.color = markercolor;
        // Update feature state with the new color
        if (map.current.getSource("custom")) {
          map.current.setFeatureState({
            source: "custom",
            sourceLayer: "data",
            id: marker.id,
          }, {
            color: markercolor,
          });
        }
      });

      // if (selected !== undefined && selected.length > 0) {



      //   const polygonId = `Polygon ${Date.now()}`; // Using current timestamp as an ID

      //   // Prepend the ID to the selected array
      //   selected.unshift({ id: polygonId });

      //   selectedPolygonsRef.current.push(selected);
      //   setSelectedPolygons(selectedPolygonsRef.current);

      //   setSelectedPolygonsArea((prevAreas) => [
      //     ...prevAreas, polygon
      //   ]);

      // }
    });

    map.current.on("click", "custom-point", function (e) {
      let featureProperties = e.features[0].properties;
      let featureId = e.features[0].id;


      if (currentPopup.current) {
        currentPopup.current.remove();
        currentPopup.current = null;
      }

      const popup = new maplibregl.Popup({ closeOnClick: false })
        .setLngLat(e.lngLat)
        .addTo(map.current);

      function updatePopup() {
        let content = "<h1>Marker Information</h1>";
        content += `<p><strong>Location ID:</strong> ${featureId}</p>`;
        for (let property in featureProperties) {
          content += `<p><strong>${property}:</strong> ${featureProperties[property]}</p>`;
        }

        popup.setHTML(content);

      }

      // Initial popup content setup
      updatePopup();

      currentPopup.current = popup;
    });



  };


  useEffect(() => {
    // Loop through each polygon in selectedPolygonsRef
    if (selectedPolygons === undefined || selectedPolygons === null || selectedPolygons.length === 0) {
      for (let i = 0; i < selectedPolygonsRef.current.length; i++) {
        const refPolygon = selectedPolygonsRef.current[i];
        refPolygon.forEach(marker => {
          marker.served = true;
          marker.editedFile = new Set();
          map.current.setFeatureState(
            {
              source: "custom",
              sourceLayer: "data",
              id: marker.id,
            },
            {
              color: colorGreen
            }
          );
        });
      }
    }
    else {
      for (let i = 0; i < selectedPolygonsRef.current.length; i++) {
        const refPolygon = selectedPolygonsRef.current[i];

        // If the entire polygon is missing in selectedPolygons, process all its markers
        if (selectedPolygons[i] === undefined || refPolygon[0] !== selectedPolygons[i][0]) {
          refPolygon.forEach(marker => {
            marker.served = true;
            marker.editedFile = new Set();
            map.current.setFeatureState(
              {
                source: "custom",
                sourceLayer: "data",
                id: marker.id,
              },
              {
                color: colorGreen
              }
            );
          });

          // Skip further processing for this polygon
          break;
        }


      }
    }

    // Sync ref with the current state
    selectedPolygonsRef.current = [...selectedPolygons];

  }, [selectedPolygons]); // Dependency on selectedPolygons





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
            color: colorGreen
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
      const url = `${backend_url}/api/served-data/${folderID}`


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
            coveredBy: item.coveredLocations ? item.coveredLocations.split(", ").map(filename => filename.trim()) : Set, // Convert string to array and trim whitespace
            color: item.served ? colorGreen : colorRed,
            editedFile: new Set()
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
      transformRequest: (url) => {
        if (url.startsWith(`${backend_url}/api/tiles/`)) {
          return {
            url: url,
            credentials: 'include' // Include cookies for cross-origin requests
          };
        }
      }
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
  }, [selectedBaseMap, folderID]);

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


  const onConfirm = (combinationToPoints, checkedState, polygonFeature) => {

    let allPoints = [];
    Object.values(combinationToPoints).forEach(points => {
      allPoints.push(...points);
    });

    if (allPoints.length > 0) {
      const polygonId = `Polygon ${Date.now()}`; // Using current timestamp as an ID

      // Update each point's coveredBy attribute based on the current state of checkboxes
      allPoints.forEach(point => {
        const editedFile = Array.from(point.coveredBy).filter(file => checkedState[Array.from(point.coveredBy).sort().join(", ")]?.[file]);
        point.editedFile = new Set(editedFile);
        // Update feature state on the map for each point
        map.current.setFeatureState({
          source: "custom",
          sourceLayer: "data",
          id: point.id,
        }, {
          color: point.color
        });
      });

      // Push updated points to your state management system
      const updatedPoints = [...allPoints];
      updatedPoints.unshift({ id: polygonId }); // Include polygon ID in the state update

      selectedPolygonsRef.current.push(updatedPoints);
      setSelectedPolygons(selectedPolygonsRef.current);
      console.log(polygonFeature);
      setSelectedPolygonsArea((prevAreas) => [
        ...prevAreas, polygonFeature
      ]);
    }


    // Additional logic to update UI or state as needed
    setCombinationToColorMap({});
  };

  const onUndo = (combinationToPoints, colorsArrayIndex) => {

    // Iterate through all points in each combination and reset their states
    Object.values(combinationToPoints).forEach(points => {


      points.forEach(point => {
        point.served = true;
        point.color = colorGreen;
        // Reset the 'served' status and color for each point
        map.current.setFeatureState({
          source: "custom",
          sourceLayer: "data",
          id: point.id,
        }, {
          color: colorGreen
        });
      });
    });

    // Reset UI related state
    setCombinationToColorMap({});

  };

  const CoverageLegend = ({ combinationToColorMap, combinationToPoints, selectedPolygonFeature, onConfirm, onUndo }) => {
    if (combinationToColorMap === undefined || Object.keys(combinationToColorMap).length === 0) {
      return null;
    }


    const [checkedState, setCheckedState] = useState(() => {
      const initialState = {};
      Object.entries(combinationToPoints).forEach(([combination, points]) => {
        if (!initialState[combination]) {
          initialState[combination] = {};
        }
        combination.split(", ").forEach(file => {
          initialState[combination][file] = true; // Initially all checkboxes are checked
        });
      });
      return initialState;
    });

    useEffect(() => {
      const newCheckedState = {};
      Object.entries(combinationToPoints).forEach(([combination, points]) => {
        if (!newCheckedState[combination]) {
          newCheckedState[combination] = {};
        }
        combination.split(", ").forEach(file => {
          // Ensure each file starts as checked, or keep existing state if already initialized
          newCheckedState[combination][file] = newCheckedState[combination][file] ?? true;
        });
      });
      setCheckedState(newCheckedState);
    }, [combinationToPoints]);

    const handleCheckboxChange = (combination, file) => {
      setCheckedState(prevState => ({
        ...prevState,
        [combination]: {
          ...prevState[combination],
          [file]: !prevState[combination][file]
        }
      }));
    };

    const handleConfirmClick = () => {
      onConfirm(combinationToPoints, checkedState, selectedPolygonFeature);
    };

    const handleUndoClick = () => {
      onUndo(combinationToPoints);
    };

    return (
      <Box sx={{ position: 'absolute', top: '10%', left: '50%', transform: 'translateX(-50%)', zIndex: 10000 }}>
        <Paper sx={{ padding: 2, backgroundColor: 'white', borderRadius: 2, boxShadow: 3, minWidth: 300 }}>
          <Typography variant="h6" gutterBottom>
            You are editing points covered by the following coverage files. Please verify and uncheck the coverage files that actually serve the points. Redraw the polygon if the desired edit cannot be made.
          </Typography>
          {Object.entries(combinationToPoints).map(([combination, points]) => (
            <Box key={combination} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <Box sx={{ height: 30, width: 30, borderRadius: '50%', bgcolor: combinationToColorMap[combination], mr: 2 }}></Box>
              {combination.split(", ").map(file => (
                <label key={file} style={{ marginRight: '10px', display: 'flex', alignItems: 'center' }}>
                  <Checkbox
                    checked={checkedState[combination]?.[file] ?? false} // Safely access checked state, default to false if undefined
                    onChange={() => handleCheckboxChange(combination, file)}
                    color="primary"
                  />
                  {file}
                </label>
              ))}
            </Box>
          ))}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
            <Button variant="contained" color="primary" onClick={handleConfirmClick}>Confirm</Button>
            <Button variant="outlined" color="secondary" onClick={handleUndoClick}>Undo</Button>
          </Box>
        </Paper>
      </Box>
    );
  };



  return (
    <div>
      <div>
        <StyledBaseMapIconButton onClick={handleBasemapMenuOpen}>
          <LayersIcon color="inherit" />
        </StyledBaseMapIconButton>
        <CoverageLegend combinationToColorMap={combinationToColorMap} combinationToPoints={combinationToPoints} selectedPolygonFeature={selectedPolygonFeature} onConfirm={onConfirm} onUndo={onUndo} />
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
        {(isLoadingForUntimedEffect) && <SmallLoadingEffect isLoading={isLoadingForUntimedEffect} message={"Getting the editing tool ready..."} />}
      </div>

      <div ref={mapContainer} style={{ height: "95vh", width: "100%" }} />
    </div>
  );
}

export default Editmap;
