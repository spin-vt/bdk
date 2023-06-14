import React from "react";

const SelectedLocationContext = React.createContext({
  location: null,
  setLocation: () => {},
});

export default SelectedLocationContext;