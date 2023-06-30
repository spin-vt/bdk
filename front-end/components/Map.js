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
  buttonServe: {
    backgroundColor: '#0ADB1F',
    '&:hover': {
      backgroundColor: '#0ab81e',
    },
  },
  buttonUnserve: {
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
    minHeight: '6vh',
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
    maxWidth: "10vw",
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
  const [selectedMarkers, setSelectedMarkers] = useState([]);

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

  const changeToServe = () => {
    setSelectedMarkers(prevMarkers => prevMarkers.map(marker => ({ ...marker, served: true })));
  };

  const changeToUnserve = () => {
    setSelectedMarkers(prevMarkers => prevMarkers.map(marker => ({ ...marker, served: false })));
  };


  const doneWithChanges = () => {
    setIsLoading(true);
    const selectedMarkerIds = selectedMarkers.map((marker) => ({ id: marker.id, served: marker.served }));

    // Send request to server to change the selected markers to served
    toggleMarkers(selectedMarkerIds)
      .finally(() => {


        if (map.current.getLayer('custom')) {
          map.current.removeLayer('custom');
        }

        if (map.current.getSource('custom')) {
          map.current.removeSource('custom');
        }

        map.current.addSource('custom', {
          type: 'vector',
          tiles: ["http://localhost:8000/tiles/{z}/{x}/{y}.pbf"],
          maxzoom: 16
        });

        map.current.addLayer({
          'id': 'custom',
          'type': 'circle',
          'source': 'custom',
          'paint': {
            'circle-radius': 3,
            'circle-color':
              [
                'case',
                ['==', ['get', 'served'], true], // if 'served' property is true
                '#46DF39', // make the circle color green
                '#FF0000', // else make the circle color red
              ]
          },
          'source-layer': 'data'
        });
        setIsDataReady(true);
        setIsLoading(false); // Set loading to false after API call
        setTimeout(() => {
          setIsDataReady(false); // This will be executed 5 seconds after setIsLoading(false)
        }, 5000);
      });

    setSelectedMarkers([]);
    toggleModalVisibility();
  };

  useEffect(() => {
    const fetchMarkers = () => {
      fetch("http://localhost:8000/served-data", {
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
          allMarkersRef.current = newMarkers; // Here's the state update
          // console.log(newMarkers); // Log newMarkers instead of allMarkers
        })
        .catch((error) => {
          console.log(error);
        });
    };
    if (allMarkersRef.current.length === 0) {
      fetchMarkers();
    }
  }, []);



  const { location } = useContext(SelectedLocationContext);
  const distinctMarkerRef = useRef(null);


  useEffect(() => {
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      //look in .env for actual key (API_TILER_KEY)
      style: 'https://api.maptiler.com/maps/streets/style.json?key=QE9g8fJij2HMMqWYaZlN',
      center: [-98.35, 39.50],
      zoom: 4
    });

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

      // For Point

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
              ['==', ['get', 'served'], true],
              '#46DF39',
              '#FF0000',
            ]
        },
        'filter': ['==', ['get', 'feature_type'], 'Point'], // Only apply this layer to points
        'source-layer': 'data'
      });

      console.log("Sending markers to create tiles")



      map.current.on('draw.create', (event) => {
        const polygon = event.features[0];

        // Convert drawn polygon to turf polygon
        const turfPolygon = turf.polygon(polygon.geometry.coordinates);

        // console.log(allMarkersRef.current);

        // Iterate over markers and select if they are inside the polygon
        const selectedMarkers = allMarkersRef.current.filter((marker) => {
          const point = turf.point([marker.longitude, marker.latitude]);
          return turf.booleanPointInPolygon(point, turfPolygon);
        });

        // console.log(selectedMarkers); // Do something with the selected markers

        setSelectedMarkers(prevMarkers => [...prevMarkers, ...selectedMarkers]); // append new markers to existing selection

        allMarkersRef.current.filter(marker => !selectedMarkers.includes(marker));

        setModalVisible(true); // Show the modal

      });

      map.current.on('click', 'custom', function (e) {
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
      const { latitude, longitude } = location;

      if (distinctMarkerRef.current) {
        distinctMarkerRef.current.remove();
      }

      distinctMarkerRef.current = new maplibregl.Marker({
        color: "#FFFFFF",
        draggable: false
      }).setLngLat([longitude, latitude])
        .addTo(map.current);

      console.log(distinctMarkerRef.current);

      map.current.flyTo({
        center: [longitude, latitude],
        zoom: 16
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
            <button className={`${classes.drawtoolbutton} ${classes.buttonServe}`} onClick={changeToServe}>Change locations status to served</button>
            <button className={`${classes.drawtoolbutton} ${classes.buttonUnserve}`} onClick={changeToUnserve}>Change locations status to unserved</button>
            <button className={`${classes.drawtoolbutton} ${classes.buttonDone}`} onClick={doneWithChanges}>Done with changes</button>
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
                control={<Switch checked={showServed} onChange={handleServedChange} />}
                label="Show Served Points"
                id="served-toggle"
              />
              <FormControlLabel
                control={<Switch checked={showUnserved} onChange={handleUnservedChange} />}
                label="Show Unserved Points"
                id="unserved-toggle"
              />

              <FormControlLabel
                control={<Switch checked={showRoutes} onChange={handleToggleRoute} />}
                label="Show Fiber Routes"
                id="route-toggle"
              />
              <FormControlLabel
                control={<Switch checked={showPolygons} onChange={handleTogglePolygon} />}
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