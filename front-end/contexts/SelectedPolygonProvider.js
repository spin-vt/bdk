import React, { useState } from "react";
import SelectedPolygonContext from "./SelectedPolygonContext";

function SelectedPolygonProvider({ children }) {
  // Initialize state as an empty 2D array
  const [selectedPolygons, setSelectedPolygons] = useState([]);

  // The value object contains the current state and the updater function
  const value = { selectedPolygons, setSelectedPolygons };
  
  return (
    <SelectedPolygonContext.Provider value={value}>
      {children}
    </SelectedPolygonContext.Provider>
  );
}

export default SelectedPolygonProvider;
