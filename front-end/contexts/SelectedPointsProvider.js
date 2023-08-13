import React, { useState } from 'react';
import SelectedPointsContext from './SelectedPointsContext';

const SelectedPointsProvider = ({ children }) => {
  const [selectedPoints, setSelectedPoints] = useState([]);
  
  // The value object contains the current state and the updater function
  const value = { selectedPoints, setSelectedPoints };
  
  return (
    <SelectedPointsContext.Provider value={value}>
      {children}
    </SelectedPointsContext.Provider>
  );
}

export default SelectedPointsProvider;