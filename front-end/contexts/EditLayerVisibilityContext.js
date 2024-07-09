import React from 'react';

// Create a context with default values
const EditLayerVisibilityContext = React.createContext({
  editLayers: [], // This will store the mapping of filename to visibility 
  setEditLayers: () => {},
});

export default EditLayerVisibilityContext;