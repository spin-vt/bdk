import React from 'react';

// Create a context with default values
const FetchTaskInfoContext = React.createContext({
  shouldFetchTaskInfo: false, // This will store the mapping of filename to visibility 
  setShouldFetchTaskInfo: () => {},
});

export default FetchTaskInfoContext;