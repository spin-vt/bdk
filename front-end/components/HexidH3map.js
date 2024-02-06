import React, { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { IconButton, Menu, MenuItem, Button } from '@mui/material';
import LayersIcon from "@mui/icons-material/Layers";
import { styled } from "@mui/material/styles";
import HexidH3mapLegend from "./HexidH3mapLegend";
import HexidH3mapDrawer from "./HexidH3mapDrawer";

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

function HexidH3map() {
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

    const formatASNData = (asnData) => {
        try {
            // Parse the ASN data, assuming it's a JSON string
            const parsedData = JSON.parse(asnData);
            // Map the parsed data to a formatted string
            return parsedData.map(asn => `${asn.ASName}: Count - ${asn.count}, Avg Throughput - ${asn.average_throughput}, Standard Deviation - ${asn.std_dev_throughput}`).join('\n\n');
        } catch (error) {
            console.error('Error parsing ASN data:', error);
            return 'Invalid data';
        }
    };

    const loadGeoJSONData = async () => {
        const response = await fetch('data.geojson');
        const data = await response.json();
        return data;
    };

    const handleMapClick = (e) => {
        // Use queryRenderedFeatures to get features at the click location
        const features = mapRef.current.queryRenderedFeatures(e.point, {
            layers: ['hex-fill-tests', 'hex-fill-throughput', 'hex-fill-std-dev'] // Use the layer id of your polygons
        });

        // If there are features, display their properties
        if (features.length) {
            const properties = features[0].properties;

            // Format the ASN data for display
            const asnInfo = formatASNData(properties.ASNames);
            const content = `
                <strong>Sum Count:</strong> ${properties.sum_count}<br>
                <strong>Average Throughput:</strong> ${properties.sum_average_throughput}<br>
                <strong>Throughput Standard Deviation:</strong> ${properties.sum_std_dev_throughput}<br>
                <strong>ASN Info:</strong><br>${asnInfo.replace(/\n/g, '<br>')}`;
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
                        ['get', 'sum_count'],
                        '#ffffcc',    // color for sum_count < first cutoff (e.g., 500)
                        100, '#ffeda0', // next color at the next cutoff (e.g., 500-2,000)
                        500, '#fed976', // and so on
                        2000, '#feb24c',
                        5000, '#fd8d3c',
                        10000, '#fc4e2a', // last color for the condensed range
                        // Beyond 20,000, the color changes are more spread out
                        15000, '#e31a1c',
                        20000, '#bd0026',
                        40000, '#800026',
                        200000, '#550019'
                    ],
                    'fill-opacity': 0.75
                }
            });

            // Add layer for average throughput (you can toggle this layer based on user input)
            map.addLayer({
                id: 'hex-fill-throughput',
                type: 'fill',
                source: 'geojson-layer',
                paint: {
                    'fill-color': [
                        'interpolate',
                        ['linear'],
                        ['get', 'sum_average_throughput'],
                        10, '#feedde',
                        50, '#fdbe85',
                        100, '#fd8d3c',
                        150, '#e6550d',
                        200, '#a63603',
                        500, '#6a2100',
                        2500, '#361100'

                    ],
                    'fill-opacity': 0.75
                },
                layout: {
                    'visibility': 'none' // Change to 'visible' to show this layer
                }
            });

            map.addLayer({
                id: 'hex-fill-std-dev',
                type: 'fill',
                source: 'geojson-layer',
                paint: {
                    'fill-color': [
                        'interpolate',
                        ['linear'],
                        ['get', 'sum_std_dev_throughput'],
                        10, '#feedde',
                        50, '#fdbe85',
                        100, '#fd8d3c',
                        150, '#e6550d',
                        200, '#a63603',
                        500, '#6a2100',
                        2500, '#361100'
                    ],
                    'fill-opacity': 0.75
                },
                layout: {
                    'visibility': 'none' // Initially hidden
                }
            });

            if (mapRef.current.getLayer('hex-fill-tests')) {
                mapRef.current.setLayoutProperty(
                    'hex-fill-tests',
                    'visibility',
                    activeLayer === 'count' ? 'visible' : 'none'
                );
            }

            if (mapRef.current.getLayer('hex-fill-throughput')) {
                mapRef.current.setLayoutProperty(
                    'hex-fill-throughput',
                    'visibility',
                    activeLayer === 'throughput' ? 'visible' : 'none'
                );
            }
            if (mapRef.current.getLayer('hex-fill-std-dev')) {
                mapRef.current.setLayoutProperty(
                    'hex-fill-std-dev',
                    'visibility',
                    activeLayer === 'std_dev' ? 'visible' : 'none'
                );
            }
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

        if (mapRef.current.getLayer('hex-fill-throughput')) {
            mapRef.current.setLayoutProperty(
                'hex-fill-throughput',
                'visibility',
                activeLayer === 'throughput' ? 'visible' : 'none'
            );
        }
        if (mapRef.current.getLayer('hex-fill-std-dev')) {
            mapRef.current.setLayoutProperty(
                'hex-fill-std-dev',
                'visibility',
                activeLayer === 'std_dev' ? 'visible' : 'none'
            );
        }
        let mapping;
        if (activeLayer == 'count') {
            mapping = [
                'Number of Tests',
                { color: '#ffffcc', range: '< 100' },
                { color: '#ffeda0', range: '100 - 500' },
                { color: '#fed976', range: '500 - 2000' },
                { color: '#fd8d3c', range: '2000 - 5000' },
                { color: '#fc4e2a', range: '5000 - 10000' },
                { color: '#e31a1c', range: '10000 - 15000' },
                { color: '#bd0026', range: '15000 - 20000' },
                { color: '#800026', range: '20000 - 40000 ' },
                { color: '#550019', range: '> 40000 ' },
                // ... Add the rest of your color ranges here
            ];
        }
        else if (activeLayer == 'throughput') {
            mapping = [
                'Average Throughput(Mbps)',
                { color: '#feedde', range: '< 10' },
                { color: '#fdbe85', range: '10 - 50' },
                { color: '#fd8d3c', range: '50 - 100' },
                { color: '#e6550d', range: '100 - 150' },
                { color: '#a63603', range: '150 - 200' },
                { color: '#6a2100', range: '200 - 500' },
                { color: '#361100', range: '> 500' },
                // ... Add the rest of your color ranges here
            ];
        }
        else {
            mapping = [
                'Throughput Standard Deviation',
                { color: '#feedde', range: '< 10' },
                { color: '#fdbe85', range: '10 - 50' },
                { color: '#fd8d3c', range: '50 - 100' },
                { color: '#e6550d', range: '100 - 150' },
                { color: '#a63603', range: '150 - 200' },
                { color: '#6a2100', range: '200 - 500' },
                { color: '#361100', range: '> 500' },
                // ... Add the rest of your color ranges here
            ];
        }
        setColorMapping(mapping);

    }, [activeLayer]);


        

    const [layerMenuAnchorEl, setLayerMenuAnchorEl] = useState(null);
    const handleLayerMenuOpen = (event) => setLayerMenuAnchorEl(event.currentTarget);


    return (
        <div>
            <HexidH3mapDrawer mapRef={mapRef}/>
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
                <MenuItem onClick={() => handleLayerChange('throughput')}>Throughput</MenuItem>
                <MenuItem onClick={() => handleLayerChange('std_dev')}>Standard Deviation</MenuItem>
            </Menu>
            <HexidH3mapLegend colorMapping={colorMapping}/>

            <div ref={mapContainer} style={{ height: "100vh", width: "100%" }} />
        </div>
    );
}

export default HexidH3map;
