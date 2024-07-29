import React from 'react';

// Create a context with default values
const ReloadMapContext = React.createContext({
  shouldReloadMap: false, // This will store the mapping of filename to visibility 
  setShouldReloadMap: () => {},
});

export default ReloadMapContext;