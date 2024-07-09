import React, { useState } from 'react';
import EditLayerVisibilityContext from './EditLayerVisibilityContext';

const EditLayerVisibilityProvider = ({ children }) => {
  const [editLayers, setEditLayers] = useState([]);
  
  // The value object contains the current state and the updater function
  const value = { editLayers, setEditLayers };
  
  return (
    <EditLayerVisibilityContext.Provider value={value}>
      {children}
    </EditLayerVisibilityContext.Provider>
  );
}

export default EditLayerVisibilityProvider;