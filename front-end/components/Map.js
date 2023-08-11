import React, { useEffect, useRef, useState, useContext } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import SelectedLocationContext from "../contexts/SelectedLocationContext";
import { Toolbar, Switch, FormControlLabel, Button } from "@material-ui/core";
import { makeStyles } from "@material-ui/core/styles";
import KeyboardDoubleArrowUpIcon from "@mui/icons-material/KeyboardDoubleArrowUp";
import * as turf from "@turf/turf";
import LoadingEffect from "./LoadingEffect";
import { styled } from "@mui/material/styles";
import { saveAs } from "file-saver";
import "@maptiler/sdk/dist/maptiler-sdk.css";
import * as maptilersdk from "@maptiler/sdk";
import "maplibre-gl/dist/maplibre-gl.css";
import { Select, MenuItem } from "@material-ui/core";
import LayersIcon from "@mui/icons-material/Layers";
import IconButton from "@material-ui/core/IconButton";
import Menu from "@material-ui/core/Menu";
import SmallLoadingEffect from "./SmallLoadingEffect";
import { useRouter } from "next/router";
import LayerVisibilityContext from "../contexts/LayerVisibilityContext";
import Swal from "sweetalert2";
import Questionnaire from "../components/Questionnaire";

const useStyles = makeStyles({
  buttonUnserve: {
    backgroundColor: "#0ADB1F",
    "&:hover": {
      backgroundColor: "#0ab81e",
    },
  },
  buttonUndo: {
    backgroundColor: "#F44B14",
    "&:hover": {
      backgroundColor: "#e33c10",
    },
  },
  buttonDone: {
    backgroundColor: "#0691DA",
    "&:hover": {
      backgroundColor: "#0277bd",
    },
  },
  expandToolbarButton: {
    top: "50%",
    position: "absolute",
    minHeight: "5vh",
    // maxHeight: '10vh',
    left: "20px",
    zIndex: 1000,
    backgroundColor: "#0691DA",
    border: "0px",
    color: "#fff",
    "&:hover": {
      backgroundColor: "#73A5C6",
    },
    borderRadius: "30px",
    paddingLeft: "20px",
    paddingRight: "20px",
    transform: `translateY(-50%)`,
  },
  wrapper: {
    position: "absolute",
    left: "10px",
    top: "55%",
    transform: `translateY(-50%)`,
    zIndex: 1000,
    display: "grid",
    alignItems: "column", // this will align items vertically in the center
    justifyContent: "center",
    maxHeight: "50vh",
    maxWidth: "20vw",
  },
  collapseToolbarContainer: {
    display: "flex",
    alignItems: "center", // this will align items vertically in the center
    justifyContent: "center",
    zIndex: 1000,
    backgroundColor: "#3A7BD5",
    color: "#fff",
    "&:hover": {
      backgroundColor: "#73A5C6",
    },
    border: "0px",
    borderRadius: "10px",
    paddingLeft: "10px",
    paddingRight: "10px",
  },
  toolbar: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    justifyContent: "center",
    // maxHeight: '10vh',
    // maxWidth: "20vw", // reduce width
    borderRadius: "20px",
    backgroundColor: "rgba(255, 255, 255, 0.8)",
    zIndex: 1000,
  },
  baseMap: {
    width: "33px",
    height: "33px",
    top: "30%",
    position: "absolute",
    left: "10px",
    zIndex: 1000,
    backgroundColor: "rgba(255, 255, 255, 1)", // lighter color theme
    color: "#333", // dark icon for visibility against light background
    "&:hover": {
      backgroundColor: "rgba(255, 255, 255, 0.9)",
    },
    borderRadius: "4px", // added back borderRadius with a smaller value
    padding: "10px", // decrease padding if it's too much
    boxShadow: "0px 1px 4px rgba(0, 0, 0, 0.3)", // subtle shadow as seen in MapLibre controls
  },
});

const IOSSwitch = styled((props) => (
  <Switch focusVisibleClassName=".Mui-focusVisible" disableRipple {...props} />
))(({ theme }) => ({
  width: 42,
  height: 26,
  padding: 0,
  "& .MuiSwitch-switchBase": {
    padding: 0,
    margin: 2,
    transitionDuration: "300ms",
    "&.Mui-checked": {
      transform: "translateX(16px)",
      color: "#fff",
      "& + .MuiSwitch-track": {
        backgroundColor: theme.palette.mode === "dark" ? "#2ECA45" : "#65C466",
        opacity: 1,
        border: 0,
      },
      "&.Mui-disabled + .MuiSwitch-track": {
        opacity: 0.5,
      },
    },
    "&.Mui-focusVisible .MuiSwitch-thumb": {
      color: "#33cf4d",
      border: "6px solid #fff",
    },
    "&.Mui-disabled .MuiSwitch-thumb": {
      color:
        theme.palette.mode === "light"
          ? theme.palette.grey[100]
          : theme.palette.grey[600],
    },
    "&.Mui-disabled + .MuiSwitch-track": {
      opacity: theme.palette.mode === "light" ? 0.7 : 0.3,
    },
  },
  "& .MuiSwitch-thumb": {
    boxSizing: "border-box",
    width: 22,
    height: 22,
  },
  "& .MuiSwitch-track": {
    borderRadius: 26 / 2,
    backgroundColor: theme.palette.mode === "light" ? "#E9E9EA" : "#39393D",
    opacity: 1,
    transition: theme.transitions.create(["background-color"], {
      duration: 500,
    }),
  },
}));

function Map({ markers }) {
  const classes = useStyles();
  const mapContainer = useRef(null);
  const map = useRef(null);
  const currentPopup = useRef(null); // Ref to store the current popup

  const [isLoadingForTimedEffect, setIsLoadingForTimedEffect] = useState(false);
  const [isDataReady, setIsDataReady] = useState(false);
  const loadingTimeInMs = 3.5 * 60 * 1000;
  const [isLoadingForUntimedEffect, setIsLoadingForUntimedEffect] =
    useState(false);

  const { layers } = useContext(LayerVisibilityContext);
  const allKmlLayerRef = useRef({});

  // Use mbtiles to determine which tiles to fetc

  const router = useRouter();

  const [popupInfo, setPopupInfo] = useState(null);
  const [showDetails, setShowDetails] = useState(false);

  const createPopupContent = (featureProperties) => {
    const container = document.createElement("div");

    const header = document.createElement("h1");
    header.textContent = "Marker Information";
    container.appendChild(header);

    const toggleBtn = document.createElement("button");
    toggleBtn.textContent = "Challenge";
    toggleBtn.addEventListener("click", () => {
      details.style.display =
        details.style.display === "none" ? "block" : "none";
    });
    container.appendChild(toggleBtn);

    const details = document.createElement("div");
    details.style.display = "none";
    Object.entries(featureProperties).map(([key, value]) => {
      const detailLine = document.createElement("p");
      detailLine.innerHTML = `<strong>${key}:</strong> ${value}`;
      details.appendChild(detailLine);
    });

    container.appendChild(details);

    return container;
  };
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

    const user = localStorage.getItem("username");
    const tilesURL = `http://bdk.cs.vt.edu/tiles/${user}/{z}/{x}/{y}.pbf`;
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

    const createPopupContent = (featureProperties) => {
      const container = document.createElement("div");

      const header = document.createElement("h1");
      header.textContent = "Marker Information";
      container.appendChild(header);

      const locationBtn = document.createElement("button");
      locationBtn.textContent = "Location Info";
      locationBtn.addEventListener("click", () => {
        locationDetails.style.display = "block";
        challengeDetails.style.display = "none";
      });
      container.appendChild(locationBtn);

      const challengeBtn = document.createElement("button");
      challengeBtn.textContent = "Challenge Info";
      challengeBtn.addEventListener("click", () => {
        challengeDetails.style.display = "block";
        locationDetails.style.display = "none";
      });
      container.appendChild(challengeBtn);

      const locationDetails = document.createElement("div");
      locationDetails.style.display = "none";
      // Here you can modify what details you want for location info
      Object.entries(featureProperties).map(([key, value]) => {
        const detailLine = document.createElement("p");
        detailLine.innerHTML = `<strong>${key}:</strong> ${value}`;
        locationDetails.appendChild(detailLine);
      });
      container.appendChild(locationDetails);

      const challengeDetails = document.createElement("div");
      challengeDetails.style.display = "none";

      const customInfo = document.createElement("p");
      customInfo.innerHTML = `
If you would like to challenge only this location, 
please submit your challenge directly on the <a href="https://broadbandmap.fcc.gov/home?version=jun2022" target="_blank" style="color: blue;">FCC Website</a>.
However, if you would like to submit a bulk challenge please click the button below to add this location to your list of challenged locations. 
<br><br>
Note: By exporting the bulk-challenge from our website, you only have 50% of the required paperwork to submit your challenge. You must also provide evidence 
to support why this location is being challenged. This can be done in a variety of ways, please refer to these links for more information: <br><br>
<ol>
  <li> <a href="https://help.bdc.fcc.gov/hc/en-us/articles/9200359586971-Bulk-Fabric-Challenge-FAQs" target="_blank" style="color: blue;">Fabric Challenge FAQ</a></li>
  <li> <a href="https://help.bdc.fcc.gov/hc/en-us/articles/13308560752155-How-to-Submit-a-Successful-Bulk-Fabric-Challenge-" target="_blank" style="color: blue;">Guide on how to submit a successful challenge</a></li>
</ol>
`;

      challengeDetails.appendChild(customInfo);
      container.appendChild(challengeDetails);

      const addButton = document.createElement("button");
      addButton.textContent = "Add to Bulk Challenge";
      addButton.addEventListener("click", function () {
        router.push('/challenge');
      });

      challengeDetails.appendChild(customInfo);
      challengeDetails.appendChild(addButton);

      return container;
    };

    Object.keys(allKmlLayerRef.current).forEach((layer) => {
      console.log(layer);
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
      } else {
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
            ["==", ["get", "feature_type"], "Polygon"],
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

      const content = createPopupContent(e.features[0].properties);

      let popup = new maplibregl.Popup({ closeOnClick: false })
        .setLngLat(e.lngLat)
        .setDOMContent(content)
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

        const content = createPopupContent(e.features[0].properties);

        let popup = new maplibregl.Popup({ closeOnClick: false })
          .setLngLat(e.lngLat)
          .setDOMContent(content)
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
      return fetch("http://bdk.cs.vt.edu/api/files", {
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
            if (file.name.endsWith(".kml")) {
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
          setIsLoadingForUntimedEffect(false);
        });
    } else {
      return Promise.resolve();
    }
  };

  const addVectorTiles = () => {
    removeVectorTiles();

    fetch("http://bdk.cs.vt.edu/api/user", {
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
          ["==", ["get", "feature_type"], "Polygon"],
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
      let content = "<h1>Marker Information</h1>";
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
  }, [selectedBaseMap]);

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
        <IconButton className={classes.baseMap} onClick={handleBasemapMenuOpen}>
          <LayersIcon color="inherit" />
        </IconButton>
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
        {(isLoadingForTimedEffect || isDataReady) && (
          <LoadingEffect
            isLoading={isLoadingForTimedEffect}
            loadingTimeInMs={loadingTimeInMs}
          />
        )}
        {isLoadingForUntimedEffect && (
          <SmallLoadingEffect isLoading={isLoadingForUntimedEffect} />
        )}
      </div>

      <div ref={mapContainer} style={{ height: "100vh", width: "100%" }} />
    </div>
  );
}

export default Map;
