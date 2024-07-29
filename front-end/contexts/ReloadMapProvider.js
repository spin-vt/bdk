import React, { useState } from 'react';
import ReloadMapContext from './ReloadMapContext';

const ReloadMapProvider = ({ children }) => {
  const [shouldReloadMap, setShouldReloadMap] = useState(false);
  
  // The value object contains the current state and the updater function
  const value = { shouldReloadMap, setShouldReloadMap };
  
  return (
    <ReloadMapContext.Provider value={value}>
      {children}
    </ReloadMapContext.Provider>
  );
}

export default ReloadMapProvider;