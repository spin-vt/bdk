import React from 'react';

// Create a context with default values
const EditMapContext = React.createContext({
  isEditingMap: false, // This will store the boolean state indicating if the map is being edited
  setEditingMap: () => {},
});

export default EditMapContext;