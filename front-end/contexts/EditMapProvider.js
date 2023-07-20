import React, { useState } from 'react';
import EditMapContext from './EditMapContext';

const EditMapProvider = ({ children }) => {
  const [isEditingMap, setEditingMap] = useState(false);
  
  // The value object contains the current state and the updater function
  const value = { isEditingMap, setEditingMap };
  
  return (
    <EditMapContext.Provider value={value}>
      {children}
    </EditMapContext.Provider>
  );
}

export default EditMapProvider;