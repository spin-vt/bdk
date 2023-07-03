import React, { useEffect, useRef, useState, useContext } from "react";
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import SelectedLocationContext from "./SelectedLocationContext";
import { Toolbar, Switch, FormControlLabel, Button } from '@material-ui/core';
import { makeStyles } from '@material-ui/core/styles';
import KeyboardDoubleArrowUpIcon from '@mui/icons-material/KeyboardDoubleArrowUp';
import MapboxDraw from '@mapbox/mapbox-gl-draw'
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css'
import * as turf from '@turf/turf';
import LoadingEffect from "./LoadingEffect";
import { styled } from '@mui/material/styles';
import { saveAs } from 'file-saver';


const useStyles = makeStyles({
  modal: {
    position: 'absolute',
    top: '5%', // adjust as needed
    left: '50%',
    zIndex: '1000',
    transform: 'translate(-50%, -50%)',
    backgroundColor: '#fff',
    boxShadow: '0px 5px 15px rgba(0, 0, 0, 0.3)',
    padding: '16px 32px',
    borderRadius: '40px', // for rounded corners
    display: 'flex',
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    maxHeight: '8vh',
    minWidth: '60vw',
  },
  drawtoolbutton: {
    margin: '8px',
    borderRadius: '20px',
    color: '#fff', // Change button text color
    border: 'none',
    cursor: 'pointer',
    padding: '10px 20px', // Change as needed
    transition: 'background-color 0.3s ease', // For smooth color transition
  },
  buttonUnserve: {
    backgroundColor: '#0ADB1F',
    '&:hover': {
      backgroundColor: '#0ab81e',
    },
  },
  buttonUndo: {
    backgroundColor: '#F44B14',
    '&:hover': {
      backgroundColor: '#e33c10',
    },
  },
  buttonDone: {
    backgroundColor: '#0691DA',
    '&:hover': {
      backgroundColor: '#0277bd',
    },
  },
  expandToolbarButton: {
    top: '50%',
    position: 'absolute',
    minHeight: '5vh',
    // maxHeight: '10vh',  
    left: '20px',
    zIndex: 1000,
    backgroundColor: '#0691DA',
    border: '0px',
    color: '#fff',
    '&:hover': {
      backgroundColor: '#73A5C6',
    },
    borderRadius: '30px',
    paddingLeft: '20px',
    paddingRight: '20px',
    transform: `translateY(-50%)`,
  },
  wrapper: {
    position: 'absolute',
    left: '30px',
    top: '50%',
    transform: `translateY(-50%)`,
    zIndex: 1000,
    display: 'grid',
    alignItems: 'column', // this will align items vertically in the center
    justifyContent: 'center',
    maxHeight: '50vh',
    maxWidth: "20vw",
  },
  collapseToolbarContainer: {
    display: 'flex',
    alignItems: 'center', // this will align items vertically in the center
    justifyContent: 'center',
    zIndex: 1000,
    backgroundColor: '#3A7BD5',
    color: '#fff',
    '&:hover': {
      backgroundColor: '#73A5C6',
    },
    border: '0px',
    borderRadius: '10px',
    paddingLeft: '10px',
    paddingRight: '10px',
  },
  toolbar: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
    justifyContent: 'center',
    // maxHeight: '10vh',
    // maxWidth: "20vw", // reduce width
    borderRadius: '20px',
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
    zIndex: 1000,
  },

});

const IOSSwitch = styled((props) => (
  <Switch focusVisibleClassName=".Mui-focusVisible" disableRipple {...props} />
))(({ theme }) => ({
  width: 42,
  height: 26,
  padding: 0,
  '& .MuiSwitch-switchBase': {
    padding: 0,
    margin: 2,
    transitionDuration: '300ms',
    '&.Mui-checked': {
      transform: 'translateX(16px)',
      color: '#fff',
      '& + .MuiSwitch-track': {
        backgroundColor: theme.palette.mode === 'dark' ? '#2ECA45' : '#65C466',
        opacity: 1,
        border: 0,
      },
      '&.Mui-disabled + .MuiSwitch-track': {
        opacity: 0.5,
      },
    },
    '&.Mui-focusVisible .MuiSwitch-thumb': {
      color: '#33cf4d',
      border: '6px solid #fff',
    },
    '&.Mui-disabled .MuiSwitch-thumb': {
      color:
        theme.palette.mode === 'light'
          ? theme.palette.grey[100]
          : theme.palette.grey[600],
    },
    '&.Mui-disabled + .MuiSwitch-track': {
      opacity: theme.palette.mode === 'light' ? 0.7 : 0.3,
    },
  },
  '& .MuiSwitch-thumb': {
    boxSizing: 'border-box',
    width: 22,
    height: 22,
  },
  '& .MuiSwitch-track': {
    borderRadius: 26 / 2,
    backgroundColor: theme.palette.mode === 'light' ? '#E9E9EA' : '#39393D',
    opacity: 1,
    transition: theme.transitions.create(['background-color'], {
      duration: 500,
    }),
  },
}));


function Map({ markers }) {

  const classes = useStyles();
  const mapContainer = useRef(null);
  const map = useRef(null);


  const [showServed, setShowServed] = useState(true);
  const [showUnserved, setShowUnserved] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [showPolygons, setShowPolygons] = useState(true);

  const [isToolbarExpanded, setIsToolbarExpanded] = useState(false);
  const [showExpandButton, setShowExpandButton] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [isDataReady, setIsDataReady] = useState(false);


  const [lastPosition, setLastPosition] = useState([37.0902, -95.7129]);
  const [lastZoom, setLastZoom] = useState(5);

  const allMarkersRef = useRef([]); // create a ref for allMarkers

  const [isModalVisible, setModalVisible] = useState(false);
  const selectedMarkersRef = useRef([]);


  const toggleMarkers = (markers) => {
    return fetch("http://localhost:8000/toggle-markers", {
      method: "POST",
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(markers)
    })
      .then((response) => response.json())
      .then((data) => {
        console.log(data.message);
      })
      .catch((error) => {
        console.log(error);
      });
  };

  const handleServedChange = (event) => {
    setShowServed(event.target.checked);
    console.log(showServed);
  }

  const handleUnservedChange = (event) => {
    setShowUnserved(event.target.checked);
    console.log(showUnserved);
  }

  const handleToggleRoute = (event) => {
    setShowRoutes(event.target.checked);
  }

  const handleTogglePolygon = (event) => {
    setShowPolygons(event.target.checked);
  }


  const toggleModalVisibility = () => {
    setModalVisible(!isModalVisible);
  };


  const changeToUnserve = () => {
    const lastList = selectedMarkersRef.current[selectedMarkersRef.current.length - 1];
    console.log(lastList);
    if (lastList !== undefined && lastList !== null) {
      lastList.forEach(marker => {
        // Update the state of the selected markers
        marker.served = false;

        // Set the feature state for each updated marker

        if (map.current && map.current.getSource('custom')) {
          // Check if the marker's feature state has been previously set
          const currentFeatureState = map.current.getFeatureState({
            source: 'custom',
            sourceLayer: 'data',
            id: marker.id
          });

          console.log(currentFeatureState);

          if (currentFeatureState.hasOwnProperty('served')) {
            // Set the 'served' feature state to false
            map.current.setFeatureState({
              source: 'custom',
              sourceLayer: 'data',
              id: marker.id
            }, {
              served: false
            });
          }
        }

      });
    }
  };

  const undoChanges = () => {
    const lastList = selectedMarkersRef.current[selectedMarkersRef.current.length - 1];
    console.log(lastList);
    if (lastList !== undefined && lastList !== null) {
      lastList.forEach(marker => {

        marker.served = true;


        // If the map and the 'custom' source have been loaded
        if (map.current && map.current.getSource('custom')) {
          // Check if the marker's feature state has been previously set
          const currentFeatureState = map.current.getFeatureState({
            source: 'custom',
            sourceLayer: 'data',
            id: marker.id
          });

          if (currentFeatureState.hasOwnProperty('served')) {
            // Set the 'served' feature state to false
            map.current.setFeatureState({
              source: 'custom',
              sourceLayer: 'data',
              id: marker.id
            }, {
              served: true
            });
          }
        }

      });
      selectedMarkersRef.current.pop();
    }
  };


  const doneWithChanges = () => {
    setIsLoading(true);
    const selectedMarkerIds = [];
    selectedMarkersRef.current.forEach((list) => {
      list.forEach((marker) => {
        selectedMarkerIds.push({ id: marker.id, served: marker.served });
      });
    });
    console.log(selectedMarkerIds);
    // Send request to server to change the selected markers to served
    toggleMarkers(selectedMarkerIds)
      .finally(() => {


        if (map.current.getLayer('custom-point')) {
          map.current.removeLayer('custom-point');
        }

        if (map.current.getLayer('custom-line')) {
          map.current.removeLayer('custom-line');
        }

        if (map.current.getLayer('custom-polygon')) {
          map.current.removeLayer('custom-polygon');
        }

        if (map.current.getSource('custom')) {
          map.current.removeSource('custom');
        }

        map.current.addSource('custom', {
          type: 'vector',
          tiles: ["http://localhost:8000/tiles/{z}/{x}/{y}.pbf"],
          maxzoom: 16
        });

        // Create a single-use event handler
        function handleSourcedata(e) {
          if (e.sourceId === 'custom' && map.current.isSourceLoaded('custom')) {
            // Immediately remove the event listener
            map.current.off('sourcedata', handleSourcedata);

            fetchMarkers().then(() => {
              addLayers();
            });
          }
        }

        // Add the single-use event handler
        map.current.on('sourcedata', handleSourcedata);


        setIsDataReady(true);
        setIsLoading(false); // Set loading to false after API call
        setTimeout(() => {
          setIsDataReady(false); // This will be executed 5 seconds after setIsLoading(false)
        }, 5000);
      });

    selectedMarkersRef.current = [];
    toggleModalVisibility();
  };

  const fetchMarkers = () => {
    return fetch("http://localhost:8000/served-data", {
      method: "GET",
    })
      .then((response) => response.json())
      .then((data) => {
        const newMarkers = data.map((item) => ({
          name: item.address,
          id: item.location_id,
          latitude: item.latitude,
          longitude: item.longitude,
          served: item.served
        }));

        console.log(newMarkers);

        // Iterate over newMarkers and set the feature state for each
        newMarkers.forEach((marker) => {
          // Only set feature state if marker.served is true
          if (marker.served) {
            // This assumes that marker.id matches the feature id in your vector tile source
            map.current.setFeatureState({
              source: 'custom',
              sourceLayer: 'data',
              id: marker.id,
            }, {
              served: marker.served // Use the served property from the marker data
            });
          }
        });

        allMarkersRef.current = newMarkers; // Here's the state update
        // console.log(newMarkers); // Log newMarkers instead of allMarkers

      })
      .catch((error) => {
        console.log(error);
      });
  };

  const addLayers = () => {
    map.current.addLayer({
      'id': 'custom-line',
      'type': 'line',
      'source': 'custom',
      'layout': {
        'line-cap': 'round',
        'line-join': 'round'
      },
      'paint': {
        'line-color': '#888',
        'line-width': 2
      },
      'filter': ['==', ['get', 'feature_type'], 'LineString'], // Only apply this layer to linestrings
      'source-layer': 'data'
    });

    map.current.addLayer({
      'id': 'custom-polygon',
      'type': 'fill',
      'source': 'custom',
      'paint': {
        'fill-color': '#42004F',
        'fill-opacity': 0.5,
      },
      'filter': ['==', ['get', 'feature_type'], 'Polygon'], // Only apply this layer to polygons
      'source-layer': 'data'
    });

    map.current.addLayer({
      'id': 'custom-point',
      'type': 'circle',
      'source': 'custom',
      'paint': {
        'circle-radius': 3,
        'circle-color':
          [
            'case',
            ['==', ['feature-state', 'served'], true], // change 'get' to 'feature-state'
            '#46DF39',
            '#FF0000',
          ]
      },
      'filter': ['==', ['get', 'feature_type'], 'Point'], // Only apply this layer to points
      'source-layer': 'data'
    });
  };

  useEffect(() => {
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      //look in .env for actual key (API_TILER_KEY)
      style: 'https://api.maptiler.com/maps/streets/style.json?key=QE9g8fJij2HMMqWYaZlN',
      center: [-98.35, 39.50],
      zoom: 4
    });
  }, []);


  const { location } = useContext(SelectedLocationContext);
  const distinctMarkerRef = useRef(null);

  useEffect(() => {

    // MapboxDraw requires the canvas's class order to have the class 
    // "mapboxgl-canvas" first in the list for the key bindings to work
    map.current.getCanvas().className = 'mapboxgl-canvas maplibregl-canvas';
    map.current.getContainer().classList.add('mapboxgl-map');
    const canvasContainer = map.current.getCanvasContainer();
    canvasContainer.classList.add('mapboxgl-canvas-container');
    if (canvasContainer.classList.contains('maplibregl-interactive')) {
      canvasContainer.classList.add('mapboxgl-interactive');
    }



    const draw = new MapboxDraw({
      displayControlsDefault: false,
      controls: {
        polygon: true,
        trash: true
      }
    });


    const originalOnAdd = draw.onAdd.bind(draw);
    draw.onAdd = (map) => {
      const controlContainer = originalOnAdd(map);
      controlContainer.classList.add('maplibregl-ctrl', 'maplibregl-ctrl-group');
      return controlContainer;
    };


    map.current.addControl(new maplibregl.NavigationControl(), 'top-left');
    map.current.addControl(new maplibregl.GeolocateControl(), 'top-left');
    map.current.addControl(new maplibregl.ScaleControl(), 'bottom-left');
    map.current.addControl(draw, 'top-left');

  }, []);



  useEffect(() => {
    if (!map.current) return; // Wait for map to initialize
    map.current.on('load', function () {


      map.current.addSource('custom', {
        type: 'vector',
        tiles: ["http://localhost:8000/tiles/{z}/{x}/{y}.pbf"],
        maxzoom: 16
      });

      // Create a single-use event handler
      function handleSourcedata(e) {
        if (e.sourceId === 'custom' && map.current.isSourceLoaded('custom')) {
          // Immediately remove the event listener
          map.current.off('sourcedata', handleSourcedata);

          fetchMarkers().then(() => {
            addLayers();
          });
        }
      }

      // Add the single-use event handler
      map.current.on('sourcedata', handleSourcedata);

      map.current.on('draw.create', (event) => {
        const polygon = event.features[0];

        // Convert drawn polygon to turf polygon
        const turfPolygon = turf.polygon(polygon.geometry.coordinates);

        // console.log(allMarkersRef.current);

        // Iterate over markers and select if they are inside the polygon
        const selected = allMarkersRef.current.filter((marker) => {
          const point = turf.point([marker.longitude, marker.latitude]);
          return turf.booleanPointInPolygon(point, turfPolygon);
        });

        // console.log(selected);
        selectedMarkersRef.current.push(selected);

        // allMarkersRef.current.filter(marker => !selectedMarkers.includes(marker));

        setModalVisible(true); // Show the modal

      });

      map.current.on('click', 'custom-point', function (e) {
        let featureProperties = e.features[0].properties;

        let content = '<h1>Marker Information</h1>';
        for (let property in featureProperties) {
          content += `<p><strong>${property}:</strong> ${featureProperties[property]}</p>`;
        }

        new maplibregl.Popup({ closeOnClick: false })
          .setLngLat(e.lngLat)
          .setHTML(content)
          .addTo(map.current);
      });


    });

  }, [markers]);


  useEffect(() => {
    if (!map.current || !map.current.isStyleLoaded()) { return };

    console.log(showServed);
    console.log(showUnserved);

    if (showRoutes) {
      map.current.setLayoutProperty('custom-line', 'visibility', 'visible');
    } else {
      map.current.setLayoutProperty('custom-line', 'visibility', 'none');
    }

    if (showPolygons) {
      map.current.setLayoutProperty('custom-polygon', 'visibility', 'visible');
    } else {
      map.current.setLayoutProperty('custom-polygon', 'visibility', 'none');
    }

    // Currently if points were change to unserved with drawing tools, when toggled showServed off it will
    // still show up on the map. This is because mapbox does not support "filter" option with feature-state. 
    // Currently there are no work around except updating the database as re-rendering also relies on the "filter"
    // option
    if (showServed && !showUnserved) {
      map.current.setLayoutProperty('custom-point', 'visibility', 'visible');
      map.current.setFilter('custom-point', ['all', ['==', ['get', 'served'], true], ['==', ['get', 'feature_type'], 'Point']]);
    } else if (!showServed && showUnserved) {
      map.current.setLayoutProperty('custom-point', 'visibility', 'visible');
      map.current.setFilter('custom-point', ['all', ['==', ['get', 'served'], false], ['==', ['get', 'feature_type'], 'Point']]);
    } else if (showServed && showUnserved) {
      map.current.setLayoutProperty('custom-point', 'visibility', 'visible');
      map.current.setFilter('custom-point', ['==', ['get', 'feature_type'], 'Point']);
    } else {
      map.current.setLayoutProperty('custom-point', 'visibility', 'none');
    }
  }, [showServed, showUnserved, showRoutes, showPolygons]);


  useEffect(() => {
    if (location && map.current) {
      const { latitude, longitude, zoomlevel } = location;

      if (distinctMarkerRef.current) {
        distinctMarkerRef.current.remove();
      }

      distinctMarkerRef.current = new maplibregl.Marker({
        color: "#FFFFFF",
        draggable: false
      }).setLngLat([longitude, latitude])
        .addTo(map.current);

      map.current.flyTo({
        center: [longitude, latitude],
        zoom: zoomlevel
      });
    }
    else {
      if (distinctMarkerRef.current) {
        distinctMarkerRef.current.remove();
        distinctMarkerRef.current = null;
      }
    }
  }, [location]);







  return (
    <div>
      <div>
        {(isLoading || isDataReady) && <LoadingEffect isLoading={isLoading} />}
        {isModalVisible && (
          <div className={classes.modal}>
            <button className={`${classes.drawtoolbutton} ${classes.buttonUnserve}`} onClick={changeToUnserve}>Change locations status to unserved</button>
            <button className={`${classes.drawtoolbutton} ${classes.buttonUndo}`} onClick={undoChanges}>Undo change</button>
            <button className={`${classes.drawtoolbutton} ${classes.buttonDone}`} onClick={doneWithChanges}>Save your changes</button>
          </div>
        )}
        {showExpandButton && (
          <button className={classes.expandToolbarButton} onClick={() => { setIsToolbarExpanded(true); setShowExpandButton(false); }}>
            Show Toolbar
          </button>
        )}
        {isToolbarExpanded && (
          <div className={classes.wrapper}>
            <Toolbar className={classes.toolbar}>
              <FormControlLabel
                control={<IOSSwitch sx={{ m: 1 }} checked={showServed} onChange={handleServedChange} />}
                label="Show Served Points"
                id="served-toggle"
              />
              <FormControlLabel
                control={<IOSSwitch sx={{ m: 1 }} checked={showUnserved} onChange={handleUnservedChange} />}
                label="Show Unserved Points"
                id="unserved-toggle"
              />

              <FormControlLabel
                control={<IOSSwitch sx={{ m: 1 }} checked={showRoutes} onChange={handleToggleRoute} />}
                label="Show Fiber Routes"
                id="route-toggle"
              />
              <FormControlLabel
                control={<IOSSwitch sx={{ m: 1 }} checked={showPolygons} onChange={handleTogglePolygon} />}
                label="Show Coverage Polygons"
                id="polygon-toggle"
              />

            </Toolbar>

            <button className={classes.collapseToolbarContainer} onClick={() => { setIsToolbarExpanded(false); setShowExpandButton(true); }}>
              <KeyboardDoubleArrowUpIcon />
              Collapse
            </button>
          </div>
        )}
      </div>

      <div ref={mapContainer} style={{ height: "100vh", width: "100%" }} />
    </div>
  );
}

export default Map;