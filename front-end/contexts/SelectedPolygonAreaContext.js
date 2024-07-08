import React from 'react';

// Create a context with default values
const SelectedPolygonAreaContext = React.createContext({
  selectedPolygonsArea: [], // Initialize as an empty 2D array
  setSelectedPolygonsArea: () => {},
});

export default SelectedPolygonAreaContext;
