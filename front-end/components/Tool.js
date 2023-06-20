import React, { useState, useRef } from "react";
import Map from "./Map";
import Upload from "./Upload";
import UploadWireless from "./UploadWireless"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faArrowLeft } from "@fortawesome/free-solid-svg-icons";
import { faArrowRight } from "@fortawesome/free-solid-svg-icons";
import styles from "../styles/Tool.module.css";
import Button from "@mui/material/Button";
import { Typography } from "@material-ui/core";
import Popover from '@mui/material/Popover';
import IconButton from '@mui/material/IconButton';
import CloseIcon from '@mui/icons-material/Close';
import Tooltip from '@mui/material/Tooltip';
import { makeStyles } from '@material-ui/core/styles';

const useStyles = makeStyles(theme => ({
  tooltip: {
    animation: `$fade-in-out 2s infinite`,
  },
  '@keyframes fade-in-out': {
    '0%': {
      opacity: 0,
    },
    '50%': {
      opacity: 1,
    },
    '100%': {
      opacity: 0,
    },
  },
}));

function Tool() {
  const [markers, setMarkers] = useState([]);
  const [expandTable, setExpandTable] = useState(false);
  const [selectedOption, setSelectedOption] = useState(null);
  const [showOptions, setShowOptions] = useState(true);

  const classes = useStyles();
  const [tooltipOpen, setTooltipOpen] = useState(true);  // new state for tooltip

  const handleCloseTooltip = () => {   // new function to close tooltip
    setTooltipOpen(false);
  }

  const fetchMarkers = (downloadSpeed, uploadSpeed, techType) => {
    fetch("http://localhost:8000/served-data", {
      method: "GET",
    })
      .then((response) => response.json())
      .then((data) => {
        const newMarkers = data.map((item) => ({
          name: item.address,
          id: item.location_id,
          download_speed: downloadSpeed,
          upload_speed: uploadSpeed,
          technology: techType,
          latitude: item.latitude,
          longitude: item.longitude,
          served: item.served
        }));
        console.log(newMarkers)
        console.log("going to set the markers")
        setMarkers(newMarkers);
      })
      .catch((error) => {
        console.log(error);
      });
  };

  const fetchMarkersWireless = (downloadSpeed, uploadSpeed, techType) => {
    fetch("http://localhost:8000/served-data-wireless", {
      method: "GET",
    })
      .then((response) => response.json())
      .then((data) => {
        const newMarkers = data.map((item) => ({
          name: item.address,
          id: item.location_id,
          download_speed: downloadSpeed,
          upload_speed: uploadSpeed,
          technology: techType,
          latitude: item.latitude,
          longitude: item.longitude,
          served: item.served,
          type: item.type

        }));
        console.log(newMarkers)
        console.log("going to set the markers")
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
    handleCloseTooltip();
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
          <Tooltip title="Click here to upload!" placement="left" open={!expandTable && tooltipOpen} classes={{ tooltip: classes.tooltip }}>
            <FontAwesomeIcon icon={expandTable ? faArrowRight : faArrowLeft} className={styles.expandIcon} />
            </Tooltip>
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
                    <div>
                      <h2>Wireless Upload Component</h2>
                      <UploadWireless fetchMarkersWireless={fetchMarkersWireless} />
                    </div>
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
