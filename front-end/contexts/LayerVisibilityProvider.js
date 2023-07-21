import React, { useState } from 'react';
import LayerVisibilityContext from './LayerVisibilityContext';

const LayerVisibilityProvider = ({ children }) => {
  const [layers, setLayers] = useState({});
  
  // The value object contains the current state and the updater function
  const value = { layers, setLayers };
  
  return (
    <LayerVisibilityContext.Provider value={value}>
      {children}
    </LayerVisibilityContext.Provider>
  );
}

export default LayerVisibilityProvider;