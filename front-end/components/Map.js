import React, { useEffect, useRef, useState, useContext } from "react";
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import SelectedLocationContext from "./SelectedLocationContext";
import { Toolbar, Switch, FormControlLabel } from '@material-ui/core';
import { makeStyles } from '@material-ui/core/styles';
import KeyboardDoubleArrowUpIcon from '@mui/icons-material/KeyboardDoubleArrowUp';


const useStyles = makeStyles({
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
    // maxHeight: '5vh',
    // maxWidth: ' 8vw',
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
  console.log(markers.length);
  const classes = useStyles();
  const mapContainer = useRef(null);
  const map = useRef(null);

  const [showServed, setShowServed] = useState(true);
  const [showUnserved, setShowUnserved] = useState(true);

  const [isToolbarExpanded, setIsToolbarExpanded] = useState(false);
  const [showExpandButton, setShowExpandButton] = useState(true);

  const [lastPosition, setLastPosition] = useState([37.0902, -95.7129]);
  const [lastZoom, setLastZoom] = useState(5);

  const handleServedChange = (event) => {
    setShowServed(event.target.checked);
    console.log(showServed);
  }

  const handleUnservedChange = (event) => {
    setShowUnserved(event.target.checked);
    console.log(showUnserved);
  }

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
    map.current.addControl(new maplibregl.NavigationControl(), 'top-left');
    map.current.addControl(new maplibregl.GeolocateControl(), 'top-left');
    map.current.addControl(new maplibregl.ScaleControl(), 'bottom-left');
  }, []);

  // const sendMarkers = () => {
  //   fetch("http://localhost:8000/tiles", {
  //     method: "POST",
  //     headers: {
  //       'Content-Type': 'application/json'
  //     },
  //     body: JSON.stringify(markers)
  //   })
  //     .then((response) => response.json())
  //     .then((data) => {
  //       console.log("Tiles created successfully");
  //     })
  //     .catch((error) => {
  //       console.log(error);
  //     });
  // };

  useEffect(() => {
    if (!map.current) return; // Wait for map to initialize
    map.current.on('load', function () {
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
          // [
            // 'case',
            // ['==', ['get', 'served'], true], // if 'served' property is true
            // '#00FF00', // make the circle color green
            '#FF0000', // else make the circle color red
          // ]
        },
        'source-layer': 'data'
      });
      console.log("Sending markers to create tiles")
      // sendMarkers();


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
    if (!map.current || !map.current.isStyleLoaded()) {return};

    console.log(showServed);
    console.log(showUnserved);

    if (showServed && !showUnserved) {
      map.current.setLayoutProperty('custom', 'visibility', 'visible');
      map.current.setFilter('custom', ['==', ['get', 'served'], true]);
    } else if (!showServed && showUnserved) {
      map.current.setLayoutProperty('custom', 'visibility', 'visible');
      map.current.setFilter('custom', ['==', ['get', 'served'], false]);
    } else if (showServed && showUnserved) {
      map.current.setLayoutProperty('custom', 'visibility', 'visible');
      map.current.setFilter('custom', null);
    } else {
      map.current.setLayoutProperty('custom', 'visibility', 'none');
    }
  }, [showServed, showUnserved]);

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
                label="Show Served"
                id="served-toggle"
              />
              <FormControlLabel
                control={<Switch checked={showUnserved} onChange={handleUnservedChange} />}
                label="Show Unserved"
                id="unserved-toggle"
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
