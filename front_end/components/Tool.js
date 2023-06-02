import React, { useState } from "react";
import Map from "./Map";
import Upload from "./Upload";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faArrowLeft } from "@fortawesome/free-solid-svg-icons";
import styles from "../styles/Tool.module.css";
import Button from "@mui/material/Button";

function Tool() {
  const [markers, setMarkers] = useState([]);
  const [expandTable, setExpandTable] = useState(false);
  const [selectedOption, setSelectedOption] = useState(null);
  const [showOptions, setShowOptions] = useState(true);

  const fetchMarkers = () => {
    fetch("http://localhost:8000/served-data", {
      method: "GET",
    })
      .then((response) => response.json())
      .then((data) => {
        const newMarkers = data.map((item) => ({
          name: item.address,
          id: item.location_id,
          latitude: item.latitude,
          longitude: item.longitude,
          served: item.served
        }));
        console.log(newMarkers)
        setMarkers(newMarkers);
      })
      .catch((error) => {
        console.log(error);
      });
  };

  const toggleUpload = () => {
    setExpandTable(!expandTable);
    setSelectedOption(null);
    setShowOptions(true);
  };

  const handleOptionClick = (option) => {
    setSelectedOption(option);
    setShowOptions(false);
  };

  const handleBack = () => {
    setSelectedOption(null);
    setShowOptions(true);
  };

  return (
    <div className={`${styles.toolContainer}`}>
      <div className={styles.content}>
        <div className={styles.mapContainer}>
          <Map markers={markers} />
          <div className={styles.iconContainer} onClick={toggleUpload}>
            <FontAwesomeIcon icon={faArrowLeft} className={styles.expandIcon} />
          </div>
        </div>
        {expandTable && (
          <div className={`${styles.sidebar} ${styles.sidebarVisible}`}>
            <div className={styles.sidebarContent}>
              {showOptions ? (
                <div>
                  <h2 className={styles.dataTypeHeading}>Select your data type:</h2>
                  <Button variant="text" onClick={() => handleOptionClick("fiber")}>
                    Fiber
                  </Button>
                  <Button variant="text" onClick={() => handleOptionClick("wireless")}>
                    Wireless
                  </Button>
                </div>
              ) : (
                <div>
                  <div className={styles.backButtonContainer}>
                    <Button
                      variant="text"
                      className={`${styles.backButton} ${styles.backButtonIcon}`}
                      onClick={handleBack}
                    >
                      <FontAwesomeIcon icon={faArrowLeft} className={styles.backButtonIcon} />
                      <h4>Go back</h4>
                    </Button>
                  </div>
                  {selectedOption === "fiber" && (
                    <div>
                      <h2>Fiber Upload Component</h2>
                      <Upload fetchMarkers={fetchMarkers} />
                    </div>
                  )}
                  {selectedOption === "wireless" && (
                    // Render the wireless upload component
                    // You can replace the placeholder text with the actual wireless upload component
                    <h2>Wireless Upload Component</h2>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default Tool;
