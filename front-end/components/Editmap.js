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
import { backend_url, maptile_street, maptile_satelite, maptile_dark } from "../utils/settings";
import SelectedPolygonContext from "../contexts/SelectedPolygonContext";
import SelectedPolygonAreaContext from "../contexts/SelectedPolygonAreaContext.js";
import { useFolder } from "../contexts/FolderContext.js";
import { Typography, Checkbox, Box, Paper, Button } from '@mui/material';
import ReloadMapContext from "../contexts/ReloadMapContext.js";


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

  const colorRed = "#FF0000";
  const colorGreen = "#46DF39";

  const { shouldReloadMap, setShouldReloadMap } = useContext(ReloadMapContext);

  const [selectedPolygonFeature, setSelectedPolygonFeature] = useState(null);

  const [selectedPointsFileNames, setSelectedPointsFilenames] = useState(new Set());
  const [selectedPoints, setSelectedPoints] = useState([]);

  const router = useRouter();

  const currentPopup = useRef(null);

  const baseMaps = {
    STREETS: maptile_street,
    SATELLITE: maptile_satelite,
    DARK: maptile_dark,
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
    setSelectedBaseMap(baseMapName);
    setShouldReloadMap(true);
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
        // const coveredByWithoutEdited = new Set([...marker.coveredBy].filter(x => !(marker.editedFile && marker.editedFile.has(x))));
        // return isInsidePolygon && (coveredByWithoutEdited.size > 0);
        return isInsidePolygon && marker.served;
      });

      if (selected.length === 0) {
        return;
      }

      // // Collect unique filenames from the selected markers
      // const filenames = new Set();
      // selected.forEach((marker) => {
      //   const coveredByWithoutEdited = new Set([...marker.coveredBy].filter(x => !(marker.editedFile && marker.editedFile.has(x))));
      //   coveredByWithoutEdited.forEach((filename) => {
      //     filenames.add(filename);
      //   });
      // });

       // Collect unique filenames from the selected markers
       const filenames = new Set();
       selected.forEach((marker) => {
         marker.coveredBy.forEach((filename) => {
           filenames.add(filename);
         });
       });

      setSelectedPolygonFeature(polygon);

      if (filenames.size === 1) {
        selected.forEach(marker => {
          marker.served = false;
          marker.color = colorRed;
          marker.editedFile = new Set(filenames);
          // Update feature state with the new color
          if (map.current.getSource("custom")) {
            map.current.setFeatureState({
              source: "custom",
              sourceLayer: "data",
              id: marker.id,
            }, {
              color: colorRed,
            });
          }
        });

        const polygonId = `Polygon ${Date.now()}`; // Using current timestamp as an ID

        // Prepend the ID to the selected array
        selected.unshift({ id: polygonId });

        selectedPolygonsRef.current.push(selected);
        setSelectedPolygons(selectedPolygonsRef.current);
        setSelectedPolygonsArea((prevAreas) => [
          ...prevAreas, polygon
        ]);
      }
      else {
        setSelectedPointsFilenames(filenames);
        setSelectedPoints(selected);
      }

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
          marker.color = colorGreen;
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
            marker.color = colorGreen;
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
          coveredBy: item.coveredLocations ? item.coveredLocations.split(", ").map(filename => filename.trim()) : [], // Convert string to array and trim whitespace
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

  };

  useEffect(() => {
    if (!shouldReloadMap) {
      return;
    }
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
      setShouldReloadMap(false);
    };
    map.current.on("load", handleBaseMapChange);

  }, [selectedBaseMap, folderID, shouldReloadMap]);

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


  const onConfirm = (selectedPoints, checkedState, polygonFeature) => {

    const polygonId = `Polygon ${Date.now()}`; // Using current timestamp as an ID

    // Update each point's coveredBy attribute based on the current state of checkboxes
    selectedPoints.forEach(point => {
      const editedFile = Array.from(point.coveredBy).filter(file => checkedState[file]);
      point.editedFile = new Set(editedFile);

      if (editedFile.length === point.coveredBy.length) {
        point.served = false;
      }
    });

    const filteredPoints = selectedPoints.filter(point => point.editedFile.size > 0);

    if (filteredPoints.length > 0) {
      // Push updated points to your state management system
      const updatedPoints = [...filteredPoints];
      updatedPoints.unshift({ id: polygonId }); // Include polygon ID in the state update

      selectedPolygonsRef.current.push(updatedPoints);
      setSelectedPolygons(selectedPolygonsRef.current);
      setSelectedPolygonsArea((prevAreas) => [
        ...prevAreas, polygonFeature
      ]);
    }

    // Additional logic to update UI or state as needed
    setSelectedPointsFilenames(new Set());
    setSelectedPoints([]);
  };

  const onUndo = (selectedPoints) => {

    selectedPoints.forEach(point => {
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


    setSelectedPointsFilenames(new Set());
    setSelectedPoints([]);

  };

  const CoverageLegend = ({ selectedPointsFileNames, selectedPoints, selectedPolygonFeature, onConfirm, onUndo }) => {
    if (!selectedPointsFileNames || selectedPointsFileNames.size < 2) {
      return null;
    }

    const colorRed = "#FF0000";
    const colorGreen = "#46DF39";
    const colorPartiallyServed = "#f5cb42";

    // Initialize checked state for each filename in selectedPointsFileNames
    const [checkedState, setCheckedState] = useState(() => {
      const initialState = {};
      selectedPointsFileNames.forEach(file => {
        initialState[file] = false; // Initially all checkboxes are unchecked
      });
      return initialState;
    });

    // Update checked state if selectedPointsFileNames changes
    useEffect(() => {
      const newCheckedState = {};
      selectedPointsFileNames.forEach(file => {
        newCheckedState[file] = checkedState[file] ?? true;
      });
      setCheckedState(newCheckedState);
    }, [selectedPointsFileNames]);

    const handleCheckboxChange = (file) => {
      setCheckedState(prevState => {
        const newState = {
          ...prevState,
          [file]: !prevState[file]
        };

        // Update colors of the points based on the new checked state
        selectedPoints.forEach(point => {
          const coveredBySet = new Set(point.coveredBy);
          const checkedFiles = new Set(Object.keys(newState).filter(f => newState[f]));
          const intersectionLength = [...checkedFiles].filter(x => coveredBySet.has(x)).length;

          let color;
          if (intersectionLength === coveredBySet.size) {
            color = colorRed;
          } else if (intersectionLength === 0) {
            color = colorGreen;
          } else {
            color = colorPartiallyServed;
          }

          point.color = color;
          // Update feature state with the new color
          if (map.current.getSource("custom")) {
            map.current.setFeatureState({
              source: "custom",
              sourceLayer: "data",
              id: point.id,
            }, {
              color: color,
            });
          }
        });

        return newState;
      });
    };

    const handleConfirmClick = () => {
      onConfirm(selectedPoints, checkedState, selectedPolygonFeature);
    };

    const handleUndoClick = () => {
      onUndo(selectedPoints);
    };

    return (
      <Box sx={{ position: 'absolute', top: '10%', left: '50%', transform: 'translateX(-50%)', zIndex: 10000 }}>
        <Paper sx={{ padding: 2, backgroundColor: 'white', borderRadius: 2, boxShadow: 3, minWidth: 300 }}>
          <Typography variant="h6" gutterBottom>
            You are editing points covered by the multiple coverage files. Please check the coverage files that you want to edit. Redraw the polygon if the desired edit cannot be made.
          </Typography>
          {Array.from(selectedPointsFileNames).map(file => (
            <Box key={file} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <label style={{ marginRight: '10px', display: 'flex', alignItems: 'center' }}>
                <Checkbox
                  checked={checkedState[file] ?? false} // Safely access checked state, default to false if undefined
                  onChange={() => handleCheckboxChange(file)}
                  color="primary"
                />
                {file}
              </label>
            </Box>
          ))}
          {/* Legend Section */}
          <Box sx={{ display: 'flex', justifyContent: 'space-around', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Box sx={{ height: 20, width: 20, borderRadius: '50%', bgcolor: colorRed, mr: 1 }}></Box>
              <Typography>Unserved</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Box sx={{ height: 20, width: 20, borderRadius: '50%', bgcolor: colorPartiallyServed, mr: 1 }}></Box>
              <Typography>Partially Served</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Box sx={{ height: 20, width: 20, borderRadius: '50%', bgcolor: colorGreen, mr: 1 }}></Box>
              <Typography>Fully Served</Typography>
            </Box>
          </Box>
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
        <CoverageLegend selectedPointsFileNames={selectedPointsFileNames} selectedPoints={selectedPoints} selectedPolygonFeature={selectedPolygonFeature} onConfirm={onConfirm} onUndo={onUndo} />
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
