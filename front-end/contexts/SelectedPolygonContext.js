import React from 'react';

// Create a context with default values
const SelectedPolygonContext = React.createContext({
  selectedPolygons: [], // Initialize as an empty 2D array
  setSelectedPolygons: () => {},
});

export default SelectedPolygonContext;
