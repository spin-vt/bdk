import React from 'react';

// Create a context with default values
const LayerVisibilityContext = React.createContext({
  layers: {}, // This will store the mapping of filename to visibility 
  setLayers: () => {},
});

export default LayerVisibilityContext;