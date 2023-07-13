import React from 'react';

// Create a context with default values
const MbtilesContext = React.createContext({
  mbtid: null, 
  setMbtid: () => {},
});

export default MbtilesContext;
