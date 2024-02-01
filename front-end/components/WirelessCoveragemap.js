import React, { useEffect, useRef, useState, useContext } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { styled } from "@mui/material/styles";
import { backend_url } from "../utils/settings";
import {
  Box,
  Button,
  Typography
} from '@mui/material';
import SmallLoadingEffect from '../components/SmallLoadingEffect';
import Swal from 'sweetalert2';

const ColorPalette = ({ mapping }) => {
  const paletteElements = Object.entries(mapping).map(([loss, rgb]) => (
    <Box
      key={loss}
      sx={{
        backgroundColor: `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`,
        width: '100%',
        height: '20px',
        margin: '2px 0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        borderRadius: '4px',
        '&:hover': {
          boxShadow: '0 4px 8px rgba(0,0,0,0.2)',
        },
        color: (theme) => theme.palette.getContrastText(`rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`),
      }}
    >
      <Typography variant="body2" component="span">
        {loss} dB
      </Typography>
    </Box>
  ));

  return (
    <Box sx={{ marginTop: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <Typography variant="subtitle1" gutterBottom align="center">
        Loss Rate (dB) to Color Mapping
      </Typography>
      {paletteElements}
    </Box>
  );
};


const WirelessCoveragemap = ({ imageUrl, transparentImageUrl, bounds, formData, colorMapping }) => {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);

  const [showCoverage, setShowCoverage] = useState(false);
  const [isLoadingForUntimedEffect, setIsLoadingForUntimedEffect] = useState(false);


  // Initialize the map
  useEffect(() => {
    mapRef.current = new maplibregl.Map({
      container: mapContainerRef.current,
      style: 'https://api.maptiler.com/maps/satellite/style.json?key=QE9g8fJij2HMMqWYaZlN',
      center: [(bounds.east + bounds.west) / 2, (bounds.north + bounds.south) / 2],
      zoom: 4, // Adjust the zoom level appropriately
      transformRequest: (url) => {
        if (url.startsWith(`${backend_url}/api/tiles/`)) {
          return {
            url: url,
            credentials: 'include' // Include cookies for cross-origin requests
          };
        }
      }
    });

    return () => {
      mapRef.current.remove();
    };
  }, []); // Empty dependency array ensures this only runs once on mount

  // Update the image overlay when imageUrl or bounds change
  useEffect(() => {
    mapRef.current.once('load', () => {
      addImageOverlay();
      if (showCoverage) {
        removeVectorTiles();
        addVectorTiles();
        fetchCoveredPoints();
      }
      else {
        removeVectorTiles();
      }
    });

    // If the map was already loaded, we need to manually trigger the update
    if (mapRef.current.isStyleLoaded()) {
      mapRef.current.fire('load');
    }
  }, [imageUrl, transparentImageUrl, bounds, showCoverage]); // This will run every time imageUrl or bounds change

  const fetchLossToColorMapping = (towerId) => {
    fetch(`${backend_url}/api/get-loss-color-mapping/${towerId}`, {
      method: "GET",
      credentials: "include",
    })
      .then((response) => {
        if (response.ok) {
          return response.json();
        } else {
          throw new Error('Failed to fetch loss to color mapping');
        }
      })
      .then((mapping) => {
        setColorMapping(mapping); // Update the state with the fetched mapping
      })
      .catch((error) => {
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: error.message,
        });
      });
  };

  const fetchAndRenderGeoJSON = (task_id) => {
    fetch(`${backend_url}/api/get-preview-geojson/${task_id}`, {
      method: "GET",
      credentials: "include", // make sure to send credentials to maintain the session
    })
      .then(response => {
        if (!response.ok) {
          throw new Error('Failed to fetch coverage data');
        }
        return response.json(); // Get the blob directly from the response
      })
      .then(geoJSONData => {
        console.log(geoJSONData);
        addGeoJSONLayer(geoJSONData); // Pass the GeoJSON data directly
      })
      .catch((error) => {
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: error.message,
        });
      });
  };

  const addGeoJSONLayer = (geojsonData) => {
    if (mapRef.current.getSource('geojson-layer')) {
      mapRef.current.removeLayer('geojson-layer');
      mapRef.current.removeSource('geojson-layer');
    }
    const geojsonObject = JSON.parse(geojsonData);
    console.log(geojsonObject);
    mapRef.current.addSource('geojson-layer', {
      type: 'geojson',
      data: geojsonObject
    });

    mapRef.current.addLayer({
      id: 'geojson-layer',
      type: 'circle', // or any other type suitable for your data
      source: 'geojson-layer',
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
        "circle-color": "#00FF00",

      },
    });
  };

  const addSource = () => {
    const existingSource = mapRef.current.getSource("custom");
    if (existingSource) {
      mapRef.current.removeSource("custom");
    }

    const tilesURL = `${backend_url}/api/tiles/{z}/{x}/{y}.pbf`;
    mapRef.current.addSource("custom", {
      type: "vector",
      tiles: [tilesURL],
      maxzoom: 16,
    });
  };

  const addLayers = () => {

    mapRef.current.addLayer({
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
        "circle-color": "#FF0000",

      },
      filter: ["==", ["get", "feature_type"], "Point"], // Only apply this layer to points
      "source-layer": "data",
    });
  };

  const removeVectorTiles = () => {
    if (mapRef.current.getLayer("custom-point")) {
      mapRef.current.removeLayer("custom-point");
    }

    if (mapRef.current.getSource("custom")) {
      mapRef.current.removeSource("custom");
    }
  };

  const addVectorTiles = () => {
    removeVectorTiles();
    addSource();
    addLayers();
    mapRef.current.on("click", "custom-point", function (e) {
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
        .addTo(mapRef.current);
    });
  };


  const addImageOverlay = () => {
    const map = mapRef.current;
    if (map && imageUrl && transparentImageUrl && bounds) {
      // Ensure the bounds are numbers
      const westBound = parseFloat(bounds.west);
      const eastBound = parseFloat(bounds.east);
      const northBound = parseFloat(bounds.north);
      const southBound = parseFloat(bounds.south);


      if (map.getSource('image-overlay')) {
        map.removeLayer('overlay');
        map.removeSource('image-overlay');
      }

      const imgUrl = showCoverage ? transparentImageUrl : imageUrl;
      // Add new image source
      map.addSource('image-overlay', {
        type: 'image',
        url: imgUrl,
        coordinates: [
          [westBound, northBound], // top left
          [eastBound, northBound], // top right
          [eastBound, southBound], // bottom right
          [westBound, southBound], // bottom left
        ],
      });

      // Add new image layer

      map.addLayer({
        id: 'overlay',
        source: 'image-overlay',
        type: 'raster',
        paint: {
          'raster-opacity': 0.85,
          'raster-fade-duration': 0,
        },
      });


      const longitude = (westBound + eastBound) / 2;
      const latitude = (northBound + southBound) / 2;
      mapRef.current.flyTo({
        center: [longitude, latitude],
        zoom: 8,
      });

    }
  }

  const fetchCoveredPoints = () => {
    if (showCoverage) {
      setIsLoadingForUntimedEffect(true);
      fetch(`${backend_url}/api/preview-wireless-prediction-fabric-coverage`, {
        method: "POST",
        headers: {
          'Content-Type': 'application/json', // Set the content type to application/json
        },
        body: JSON.stringify(formData), // Serialize formData to JSON
        credentials: "include",
      })
        .then((response) => {
          if (response.status === 401) {
            setIsLoadingForUntimedEffect(false);
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
          } else if (response.status === 500 || response.status === 400) {
            setIsLoadingForUntimedEffect(false);
            toast.error(
              "There is an error on our end",
              {
                position: toast.POSITION.TOP_RIGHT,
                autoClose: 10000,
              }
            );
          }
        })
        .then((data) => {
          if (data) {
            const intervalId = setInterval(() => {
              fetch(`${backend_url}/api/status/${data.task_id}`)
                .then((statusResponse) => statusResponse.json())
                .then((status) => {
                  if (status.state === "SUCCESS") {
                    // Task is complete, handle the points data
                    setIsLoadingForUntimedEffect(false);
                    clearInterval(intervalId);

                    console.log(status);
                    const statusObject = JSON.parse(status.status.replace(/'/g, "\""));
                    console.log(statusObject);
                    fetchAndRenderGeoJSON(statusObject.geojson_filename); // Now 'pointsData' is a JavaScript object


                  } else if (status.state === "FAILURE") {
                    // Handle failure
                    setIsLoadingForUntimedEffect(false);
                    clearInterval(intervalId);
                    console.error("Task failed with error:", status.status);
                  }
                });
            }, 5000);
          }
        })
        .catch((error) => {
          setIsLoadingForUntimedEffect(false);
          Swal.fire({
            icon: "error",
            title: "Oops...",
            text: "There is an error on our end, please try again later",
          });
          console.error("Error:", error);

        });
    }
  }

  const toggleCoverageView = () => {
    setShowCoverage(!showCoverage);
  };


  return (
    <div>
      <div>
        {(isLoadingForUntimedEffect) && <SmallLoadingEffect isLoading={isLoadingForUntimedEffect} message={"Computing the fabric locations your tower covers"} />}
      </div>
      <div style={{ display: 'flex', justifyContent: 'center', margin: '10px 0' }}>
        {(imageUrl) && <Button variant="contained" color="success" onClick={toggleCoverageView}>
          {showCoverage ? 'View Heatmap' : "Preview Tower's Fabric Locations Coverage"}
        </Button>
        }
      </div>
      <div ref={mapContainerRef} style={{ height: '600px', width: '100%' }} />

      {(!showCoverage && imageUrl) &&
        <ColorPalette mapping={colorMapping} />}
    </div>
  );
};

export default WirelessCoveragemap;