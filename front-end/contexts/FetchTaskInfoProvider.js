import React, { useState } from 'react';
import FetchTaskInfoContext from './FetchTaskInfoContext';

const FetchTaskInfoProvider = ({ children }) => {
  const [shouldFetchTaskInfo, setShouldFetchTaskInfo] = useState(false);
  
  // The value object contains the current state and the updater function
  const value = { shouldFetchTaskInfo, setShouldFetchTaskInfo };
  
  return (
    <FetchTaskInfoContext.Provider value={value}>
      {children}
    </FetchTaskInfoContext.Provider>
  );
}

export default FetchTaskInfoProvider;