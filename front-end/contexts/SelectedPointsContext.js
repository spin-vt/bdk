import React from 'react';

// Create a context with default values
const SelectedPointsContext = React.createContext({
  selectedPoints: [], 
  setSelectedPoints: () => {},
});

export default SelectedPointsContext;