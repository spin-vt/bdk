import React, { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { IconButton, Menu, MenuItem, Button } from '@mui/material';
import LayersIcon from "@mui/icons-material/Layers";
import { styled } from "@mui/material/styles";
import ChallengeH3mapLegend from "./ChallengeH3mapLegend";
import ChallengeH3mapDrawer from "./ChallengeH3mapDrawer";

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

function ChallengeH3map() {
    const mapRef = useRef(null);
    const mapContainer = useRef(null);
    const [selectedBaseMap, setSelectedBaseMap] = useState("STREETS");
    const [basemapAnchorEl, setBasemapAnchorEl] = useState(null);

    const [activeLayer, setActiveLayer] = useState('count'); // 'count' or 'throughput'
    const [colorMapping, setColorMapping] = useState([]);


    const baseMaps = {
        STREETS: "https://api.maptiler.com/maps/streets/style.json?key=QE9g8fJij2HMMqWYaZlN",
        SATELLITE: "https://api.maptiler.com/maps/satellite/style.json?key=QE9g8fJij2HMMqWYaZlN",
        DARK: "https://api.maptiler.com/maps/backdrop-dark/style.json?key=QE9g8fJij2HMMqWYaZlN",
    };

    const handleBasemapMenuOpen = (event) => setBasemapAnchorEl(event.currentTarget);
    const handleBasemapMenuClose = () => setBasemapAnchorEl(null);
    const handleBaseMapToggle = (baseMapName) => {
        setSelectedBaseMap(baseMapName);
        setBasemapAnchorEl(null);
    };

    const handleLayerChange = (layerName) => {
        setActiveLayer(layerName);
        setLayerMenuAnchorEl(null); // Assuming you've added a state for the anchor of the layers' menu
    };


    const loadGeoJSONData = async () => {
        const response = await fetch('challenge_data.geojson');
        const data = await response.json();
        return data;
    };

    const handleMapClick = (e) => {
        // Use queryRenderedFeatures to get features at the click location
        const features = mapRef.current.queryRenderedFeatures(e.point, {
            layers: ['hex-fill-tests', 'hex-fill-success-rate'] // Use the layer id of your polygons
        });

        // If there are features, display their properties
        if (features.length) {
            let featureProperties = features[0].properties;
            let content = "<h1>Marker Information</h1>";
            for (let property in featureProperties) {
                content += `<p><strong>${property}:</strong> ${featureProperties[property]}</p>`;
            }
            // Create and show the popup
            new maplibregl.Popup({ closeOnClick: false })
                .setLngLat(e.lngLat)
                .setHTML(content)
                .addTo(mapRef.current);
        }
    };

    useEffect(() => {
        const map = new maplibregl.Map({
            container: mapContainer.current,
            style: baseMaps[selectedBaseMap],
            center: [-98.35, 39.5], // Default center
            zoom: 4,
        });

        mapRef.current = map;

        map.on('load', async () => {
            const geojsonData = await loadGeoJSONData();
            map.addSource('geojson-layer', {
                type: 'geojson',
                data: geojsonData
            });

            // Add layer for number of speed tests
            map.addLayer({
                id: 'hex-fill-tests',
                type: 'fill',
                source: 'geojson-layer',
                paint: {
                    'fill-color': [
                        'step',
                        ['get', 'challenge_counts'],
                        '#ffffcc',    // color for sum_count < first cutoff (e.g., 500)
                        10, '#ffeda0', // next color at the next cutoff (e.g., 500-2,000)
                        50, '#fed976', // and so on
                        100, '#feb24c',
                        200, '#fd8d3c',
                        400, '#fc4e2a', // last color for the condensed range
                        // Beyond 20,000, the color changes are more spread out
                        600, '#e31a1c',
                        800, '#bd0026',
                        1000, '#800026',
                        2000, '#550019'
                    ],
                    'fill-opacity': 0.75
                }
            });

            // Add layer for average throughput (you can toggle this layer based on user input)
            map.addLayer({
                id: 'hex-fill-success-rate',
                type: 'fill',
                source: 'geojson-layer',
                paint: {
                    'fill-color': [
                        'interpolate',
                        ['linear'],
                        ['get', 'pct_failed_challenges'],
                        0.1, '#feedde',
                        0.2, '#fdbe85',
                        0.4, '#fd8d3c',
                        0.6, '#e6550d',
                        0.8, '#a63603',
                        0.9, '#6a2100',
                        1, '#361100'

                    ],
                    'fill-opacity': 0.75
                },
                layout: {
                    'visibility': 'none' // Change to 'visible' to show this layer
                }
            });

            // map.addLayer({
            //     id: 'hex-fill-std-dev',
            //     type: 'fill',
            //     source: 'geojson-layer',
            //     paint: {
            //         'fill-color': [
            //             'interpolate',
            //             ['linear'],
            //             ['get', 'sum_std_dev_throughput'],
            //             10, '#feedde',
            //             50, '#fdbe85',
            //             100, '#fd8d3c',
            //             150, '#e6550d',
            //             200, '#a63603',
            //             500, '#6a2100',
            //             2500, '#361100'
            //         ],
            //         'fill-opacity': 0.75
            //     },
            //     layout: {
            //         'visibility': 'none' // Initially hidden
            //     }
            // });

            if (mapRef.current.getLayer('hex-fill-tests')) {
                mapRef.current.setLayoutProperty(
                    'hex-fill-tests',
                    'visibility',
                    activeLayer === 'count' ? 'visible' : 'none'
                );
            }

            if (mapRef.current.getLayer('hex-fill-success-rate')) {
                mapRef.current.setLayoutProperty(
                    'hex-fill-success-rate',
                    'visibility',
                    activeLayer === 'successrate' ? 'visible' : 'none'
                );
            }
            // if (mapRef.current.getLayer('hex-fill-std-dev')) {
            //     mapRef.current.setLayoutProperty(
            //         'hex-fill-std-dev',
            //         'visibility',
            //         activeLayer === 'std_dev' ? 'visible' : 'none'
            //     );
            // }
            mapRef.current.on('click', handleMapClick);


        });


        return () => map.remove();
    }, [selectedBaseMap]);

    useEffect(() => {
        if (mapRef.current.getLayer('hex-fill-tests')) {
            mapRef.current.setLayoutProperty(
                'hex-fill-tests',
                'visibility',
                activeLayer === 'count' ? 'visible' : 'none'
            );
        }

        if (mapRef.current.getLayer('hex-fill-success-rate')) {
            mapRef.current.setLayoutProperty(
                'hex-fill-success-rate',
                'visibility',
                activeLayer === 'successrate' ? 'visible' : 'none'
            );
        }
        // if (mapRef.current.getLayer('hex-fill-std-dev')) {
        //     mapRef.current.setLayoutProperty(
        //         'hex-fill-std-dev',
        //         'visibility',
        //         activeLayer === 'std_dev' ? 'visible' : 'none'
        //     );
        // }
        let mapping;
        if (activeLayer == 'count') {
            mapping = [
                'Number of Challenges',
                { color: '#ffffcc', range: '< 10' },
                { color: '#ffeda0', range: '10 - 50' },
                { color: '#fed976', range: '50 - 100' },
                { color: '#fd8d3c', range: '100 - 200' },
                { color: '#fc4e2a', range: '200 - 400' },
                { color: '#e31a1c', range: '400 - 600' },
                { color: '#bd0026', range: '600 - 800' },
                { color: '#800026', range: '800 - 1000 ' },
                { color: '#550019', range: '> 1000 ' },
                // ... Add the rest of your color ranges here
            ];
        }
        else if (activeLayer == 'successrate') {
            mapping = [
                'ISP failed Rate (Challenge Success Rate) (%)',
                { color: '#feedde', range: '< 10' },
                { color: '#fdbe85', range: '10 - 20' },
                { color: '#fd8d3c', range: '20 - 40' },
                { color: '#e6550d', range: '40 - 60' },
                { color: '#a63603', range: '60 - 80' },
                { color: '#6a2100', range: '80 - 90' },
                { color: '#361100', range: '90-100' },
                // ... Add the rest of your color ranges here
            ];
        }
        // else {
        //     mapping = [
        //         'Throughput Standard Deviation',
        //         { color: '#feedde', range: '< 10' },
        //         { color: '#fdbe85', range: '10 - 50' },
        //         { color: '#fd8d3c', range: '50 - 100' },
        //         { color: '#e6550d', range: '100 - 150' },
        //         { color: '#a63603', range: '150 - 200' },
        //         { color: '#6a2100', range: '200 - 500' },
        //         { color: '#361100', range: '> 500' },
        //         // ... Add the rest of your color ranges here
        //     ];
        // }
        setColorMapping(mapping);

    }, [activeLayer]);




    const [layerMenuAnchorEl, setLayerMenuAnchorEl] = useState(null);
    const handleLayerMenuOpen = (event) => setLayerMenuAnchorEl(event.currentTarget);


    return (
        <div>
            <ChallengeH3mapDrawer mapRef={mapRef} />
            <StyledBaseMapIconButton onClick={handleBasemapMenuOpen}>
                <LayersIcon />
            </StyledBaseMapIconButton>
            <Menu
                id="basemap-menu"
                anchorEl={basemapAnchorEl}
                open={Boolean(basemapAnchorEl)}
                onClose={handleBasemapMenuClose}
            >
                {Object.keys(baseMaps).map((name) => (
                    <MenuItem key={name} onClick={() => handleBaseMapToggle(name)}>
                        {name}
                    </MenuItem>
                ))}
            </Menu>
            <Button onClick={handleLayerMenuOpen}>Select Layer</Button>
            <Menu
                id="layer-menu"
                anchorEl={layerMenuAnchorEl}
                open={Boolean(layerMenuAnchorEl)}
                onClose={() => setLayerMenuAnchorEl(null)}
            >
                <MenuItem onClick={() => handleLayerChange('count')}>Count</MenuItem>
                <MenuItem onClick={() => handleLayerChange('successrate')}>Success Rate</MenuItem>
                {/* <MenuItem onClick={() => handleLayerChange('std_dev')}></MenuItem> */}
            </Menu>
            <ChallengeH3mapLegend colorMapping={colorMapping} />

            <div ref={mapContainer} style={{ height: "100vh", width: "100%" }} />
        </div>
    );
}

export default ChallengeH3map;
