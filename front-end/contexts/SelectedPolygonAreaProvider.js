import React, { useState } from "react";
import SelectedPolygonAreaContext from "./SelectedPolygonAreaContext";

function SelectedPolygonAreaProvider({ children }) {
  // Initialize state as an empty 2D array
  const [selectedPolygonsArea, setSelectedPolygonsArea] = useState([]);

  // The value object contains the current state and the updater function
  const value = { selectedPolygonsArea, setSelectedPolygonsArea };
  
  return (
    <SelectedPolygonAreaContext.Provider value={value}>
      {children}
    </SelectedPolygonAreaContext.Provider>
  );
}

export default SelectedPolygonAreaProvider;