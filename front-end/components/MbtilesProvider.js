import React, { useState } from 'react';
import MbtilesContext from './MbtilesContext';

const MbtilesProvider = ({ children }) => {
  const [mbtid, setMbtid] = useState(null);
  
  // The value object contains the current state and the updater function
  const value = { mbtid, setMbtid };
  
  return (
    <MbtilesContext.Provider value={value}>
      {children}
    </MbtilesContext.Provider>
  );
}

export default MbtilesProvider;