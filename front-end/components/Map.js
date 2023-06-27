import React, { useEffect, useRef } from "react";
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

function Map({ markers }) {
  console.log(markers.length)
  const mapContainer = useRef(null);
  const map = useRef(null);

  useEffect(() => {
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      //look in .env for actual key (API_TILER_KEY)
      style: 'https://api.maptiler.com/maps/streets/style.json?key=123',
      center: [-98.35, 39.50],
      zoom: 4
    });
    map.current.addControl(new maplibregl.NavigationControl(), 'top-left');
    map.current.addControl(new maplibregl.GeolocateControl(), 'top-left');
    map.current.addControl(new maplibregl.ScaleControl(), 'bottom-left');
  }, []);

  const sendMarkers = () => {
    fetch("http://localhost:8000/tiles", {
      method: "POST",
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(markers)
    })
      .then((response) => response.json())
      .then((data) => {
        console.log("Tiles created successfully");
      })
      .catch((error) => {
        console.log(error);
      });
  };

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
          'circle-color': [
            'case',
            ['==', ['get', 'served'], true], // if 'served' property is true
            '#00FF00', // make the circle color green
            '#FF0000' // else make the circle color purple
          ]
        },
        'source-layer': 'data'  
      });
      console.log("Sending markers to create tiles")
      sendMarkers();

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

  return (
    <div ref={mapContainer} style={{ height: "100vh", width: "100%" }} />
  );
}

export default Map;
