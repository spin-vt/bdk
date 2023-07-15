import React, { useState } from "react";
import SelectedLocationContext from "./SelectedLocationContext";

function SelectedLocationProvider({ children }) {
  const [location, setLocation] = useState(null);
  
  // The value object contains the current state and the updater function
  const value = { location, setLocation };
  
  return (
    <SelectedLocationContext.Provider value={value}>
      {children}
    </SelectedLocationContext.Provider>
  );
}

export default SelectedLocationProvider;