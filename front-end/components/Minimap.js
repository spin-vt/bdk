import React, { useEffect, useRef, useState, useContext } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Menu, IconButton, MenuItem } from '@mui/material';
import LayersIcon from "@mui/icons-material/Layers";
import SelectedLocationContext from '../contexts/SelectedLocationContext'
import { backend_url, maptile_street, maptile_satelite, maptile_dark } from "../utils/settings";
import { styled } from "@mui/material/styles";

const StyledBaseMapIconButton = styled(IconButton)({
    width: "33px",
    height: "33px",
    top: "25vh",
    position: "relative",
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


function Minimap({ id }) {
    const mapContainer = useRef(null);
    const map = useRef(null);
    const baseMaps = {
        STREETS: maptile_street,
        SATELLITE: maptile_satelite,
        DARK: maptile_dark,
    };

    const [selectedBaseMap, setSelectedBaseMap] = useState("STREETS");

    const [basemapAnchorEl, setBasemapAnchorEl] = useState(null);

    const { location } = useContext(SelectedLocationContext);
    const distinctMarkerRef = useRef(null);

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

        const tilesURL = `${backend_url}/api/tiles/${id}/{z}/{x}/{y}.pbf`;
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
            ], // Only apply this layer to polygons
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
                    ["==", ["get", "served"], true], // change 'get' to 'feature-state'
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
        addLayers();
        map.current.on("click", "custom-point", function (e) {
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
        // });
    };

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
        // Add a clean-up function that runs when the component is unmounted
        return () => {
            map.current.off("load", handleBaseMapChange);
            map.current.remove(); // This removes the map instance and any attached event listeners
        };
    }, [selectedBaseMap, id]);

    useEffect(() => {
        if (!map.current) return; // Wait for map to initialize
        // setTimeout(() => {
        map.current.resize(); // Resize map when container size changes
        //   }, 200);
    }, [id]); // Depend on 'id', so this runs whenever 'id' changes

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
export default Minimap;