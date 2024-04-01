import React, { useEffect, useRef, useState, useContext } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import SelectedLocationContext from "../contexts/SelectedLocationContext";
import { MenuItem, IconButton, Menu } from "@mui/material";
import { styled } from '@mui/material/styles';
import LoadingEffect from "./LoadingEffect";
import "@maptiler/sdk/dist/maptiler-sdk.css";
import * as maptilersdk from "@maptiler/sdk";
import LayersIcon from "@mui/icons-material/Layers";
import SmallLoadingEffect from "./SmallLoadingEffect";
import { useRouter } from "next/router";
import LayerVisibilityContext from "../contexts/LayerVisibilityContext";
import {useDeadline} from '../contexts/DeadlineContext';
import Swal from "sweetalert2";
import { backend_url } from "../utils/settings";

const StyledBaseMapIconButton = styled(IconButton)({
  width: "33px",
  height: "33px",
  top: "30%",
  position: "absolute",
  left: "10px",
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

function Map() {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const currentPopup = useRef(null); // Ref to store the current popup

  const [isDataReady, setIsDataReady] = useState(false);
  const loadingTimeInMs = 3.5 * 60 * 1000;

  const {deadline, setDeadline} = useDeadline();

  const { layers } = useContext(LayerVisibilityContext);
  const allKmlLayerRef = useRef({});

  // Use mbtiles to determine which tiles to fetch

  const router = useRouter();

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

    const tilesURL = `${backend_url}/api/tiles/{z}/{x}/{y}.pbf`;
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
        lineColor = "#FF00F7";
        fillColor = "#565EC1";
        break;
      case "DARK":
        lineColor = "#FF00F7";
        fillColor = "#565EC1";
        break;
      default:
        lineColor = "#888";
        fillColor = "#42004F";
    }


    Object.keys(allKmlLayerRef.current).forEach((layer) => {
      if (allKmlLayerRef.current[layer][0] === "wired") {
        map.current.addLayer({
          id: `wired-${layer}`,
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
          filter: [
            "all",
            ["==", ["get", "feature_type"], "LineString"],
            ["==", ["get", "network_coverages"], layer],
          ],
          "source-layer": "data",
        });
      }
    });

    // Now add all wireless layers
    Object.keys(allKmlLayerRef.current).forEach((layer) => {
      if (allKmlLayerRef.current[layer][0] !== "wired") {
        map.current.addLayer({
          id: `wireless-${layer}`,
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
            ["==", ["get", "network_coverages"], layer],
          ],
          "source-layer": "data",
        });
      }
    });

    map.current.addLayer({
      id: "unserved-points",
      type: "circle",
      source: "custom",
      paint: {
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["zoom"],
          5,
          0.5,
          12,
          2,
          15,
          3,
        ],
        "circle-color": [
          "case",
          ["==", ["get", "bsl"], "True"],
          "#FF4040",
          "#FFA840",
        ],
      },
      filter: ["all", ["==", ["get", "feature_type"], "Point"]],
      "source-layer": "data",
    });

    map.current.on("click", "unserved-points", function (e) {
      if (currentPopup.current) {
        currentPopup.current.remove();
        currentPopup.current = null;
      }

      let featureProperties = e.features[0].properties;
      let featureId = e.features[0].id;
      let content = "<h1>Marker Information</h1>";
      content += `<p><strong>Location ID:</strong> ${featureId}</p>`;
      for (let property in featureProperties) {
        content += `<p><strong>${property}:</strong> ${featureProperties[property]}</p>`;
      }

      let popup = new maplibregl.Popup({ closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(content)
        .addTo(map.current);

      currentPopup.current = popup;
    });

    Object.keys(allKmlLayerRef.current).forEach((layer) => {
      console.log(layer);
      map.current.addLayer({
        id: `served-points-${layer}`,
        type: "circle",
        source: "custom",
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            5,
            0.5,
            12,
            2,
            15,
            3,
          ],
          "circle-color": "#46DF39",
        },
        filter: [
          "all",
          ["==", ["get", "feature_type"], "Point"],
          ["in", layer, ["get", "network_coverages"]],
        ],
        "source-layer": "data",
      });

      map.current.on("click", `served-points-${layer}`, function (e) {
        if (currentPopup.current) {
          currentPopup.current.remove();
          currentPopup.current = null;
        }

        let featureProperties = e.features[0].properties;
        let featureId = e.features[0].id;
        let content = "<h1>Marker Information</h1>";
        content += `<p><strong>Location ID:</strong> ${featureId}</p>`;
        for (let property in featureProperties) {
          content += `<p><strong>${property}:</strong> ${featureProperties[property]}</p>`;
        }

        let popup = new maplibregl.Popup({ closeOnClick: false })
          .setLngLat(e.lngLat)
          .setHTML(content)
          .addTo(map.current);

        currentPopup.current = popup;
      });
    });
  };

  const removeVectorTiles = () => {
    if (map.current.getLayer("unserved-points")) {
      map.current.removeLayer("unserved-points");
    }
    Object.keys(allKmlLayerRef.current).forEach((layer) => {
      if (map.current.getLayer(`served-points-${layer}`)) {
        map.current.removeLayer(`served-points-${layer}`);
      }
      if (allKmlLayerRef.current[layer][0] === "wired") {
        if (map.current.getLayer(`wired-${layer}`)) {
          map.current.removeLayer(`wired-${layer}`);
        }
      } else {
        if (map.current.getLayer(`wireless-${layer}`)) {
          map.current.removeLayer(`wireless-${layer}`);
        }
      }
    });

    if (map.current.getSource("custom")) {
      map.current.removeSource("custom");
    }
  };
  const fetchFiles = () => {
    if (
      allKmlLayerRef.current === undefined ||
      allKmlLayerRef.current === null ||
      Object.keys(allKmlLayerRef.current).length === 0
    ) {
      return fetch(`${backend_url}/api/files?deadline=${deadline}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include", // Include cookies in the request
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
            return;
          } else if (response.status === 200) {
            return response.json();
          }
        })
        .then((data) => {
          const newLayers = data.reduce((layers, file) => {
            if (file.name.endsWith(".kml") || file.name.endsWith(".geojson")) {
              return {
                ...layers,
                [file.name]: [file.type, true], // Set the visibility of the layer to true
              };
            }
            return layers;
          }, {});

          allKmlLayerRef.current = newLayers;
        })
        .catch((error) => {
          console.log(error);
        });
    } else {
      return Promise.resolve();
    }
  };

  const addVectorTiles = () => {
    removeVectorTiles();
    if(deadline === ""){
      return
    }

    fetch(`${backend_url}/api/user`, {
      method: "GET",
      credentials: "include", // Include cookies in the request
      headers: {
        Accept: "application/json",
      },
    })
      .then((response) => {
        if (!response.ok) {

          throw new Error("Network response was not ok");
        }
        return response.json();
      })
      .then((data) => {
        console.log(data);
        addSource();
        function handleSourcedata(e) {
          if (e.sourceId === "custom" && map.current.isSourceLoaded("custom")) {
            map.current.off("sourcedata", handleSourcedata);
            fetchFiles().then(() => {
              addLayers();
            });
          }
        }
        map.current.on("sourcedata", handleSourcedata);
      })
      .catch((error) => {
        console.log(
          "There has been a problem with your fetch operation: ",
          error
        );
      });
  };

  const addSingleLayer = (layername, featuretype) => {
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
    if (featuretype === "wired") {
      map.current.addLayer({
        id: `wired-${layername}`,
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
        filter: [
          "all",
          ["==", ["get", "feature_type"], "LineString"],
          ["==", ["get", "network_coverages"], layername],
        ], // Only apply this layer to linestrings
        "source-layer": "data",
      });
    } else {
      map.current.addLayer({
        id: `wireless-${layername}`,
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
          ["==", ["get", "network_coverages"], layername],
        ], // Only apply this layer to polygons
        "source-layer": "data",
      });
    }

    map.current.addLayer({
      id: `served-points-${layername}`,
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
        "circle-color": "#46DF39",
      },
      filter: [
        "all",
        ["==", ["get", "feature_type"], "Point"], // Only apply this layer to points
        ["in", layername, ["get", "network_coverages"]],
      ],
      "source-layer": "data",
    });
    map.current.on("click", `served-points-${layername}`, function (e) {
      let featureProperties = e.features[0].properties;
      let featureId = e.features[0].id;
      let content = "<h1>Marker Information</h1>";
      content += `<p><strong>Location ID:</strong> ${featureId}</p>`;
      for (let property in featureProperties) {
        content += `<p><strong>${property}:</strong> ${featureProperties[property]}</p>`;
      }

      new maplibregl.Popup({ closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(content)
        .addTo(map.current);
    });
  };

  const removeSingleLayer = (layername, featuretype) => {
    if (map.current.getLayer(`served-points-${layername}`)) {
      map.current.removeLayer(`served-points-${layername}`);
    }
    if (featuretype === "wired") {
      if (map.current.getLayer(`wired-${layername}`)) {
        map.current.removeLayer(`wired-${layername}`);
      }
    } else {
      if (map.current.getLayer(`wireless-${layername}`)) {
        map.current.removeLayer(`wireless-${layername}`);
      }
    }
  };

  useEffect(() => {
    Object.keys(allKmlLayerRef.current).forEach((key) => {
      if (layers[key] && !allKmlLayerRef.current[key][1]) {
        // Layer should be visible but isn't, so add it
        addSingleLayer(key, allKmlLayerRef.current[key][0]);
        allKmlLayerRef.current[key][1] = true;
      } else if (!layers[key] && allKmlLayerRef.current[key][1]) {
        // Layer shouldn't be visible but is, so remove it
        removeSingleLayer(key, allKmlLayerRef.current[key][0]);
        allKmlLayerRef.current[key][1] = false;
      }
    });
  }, [layers]);

  useEffect(() => {
    const initialStyle = baseMaps[selectedBaseMap];
    console.log(initialStyle);
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

    //Remove the existing vector tile layer and source if they exist

    map.current.addControl(new maplibregl.NavigationControl(), "top-left");
    map.current.addControl(new maplibregl.GeolocateControl(), "top-left");
    map.current.addControl(new maplibregl.ScaleControl(), "bottom-left");
    // When the base map changes, remove the existing vector tiles and add the new ones
    const handleBaseMapChange = () => {
      removeVectorTiles();
      addVectorTiles();
    };
    map.current.on("load", handleBaseMapChange);
  }, [selectedBaseMap, deadline]);

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

      <div ref={mapContainer} style={{ height: "100vh", width: "100%" }} />
    </div>
  );
}

export default Map;
