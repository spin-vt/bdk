import React, { useState, useRef } from "react";
import Map from "./Map";
import Upload from "./UploadWired";
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
import Grow from '@mui/material/Grow';  // Import Grow for transition effect
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord'; // Fiber icon
import WifiIcon from '@mui/icons-material/Wifi';  // Wifi icon

const useStyles = makeStyles((theme) => ({
  sidebar: {
    backgroundColor: '#FFFFFF',
    padding: theme.spacing(2),
    boxShadow: '2px 0px 10px rgba(0, 0, 0, 0.1)',
    transition: 'transform 0.3s ease-in-out',
    transform: 'translateX(0)',
  },
  sidebarHidden: {
    transform: 'translateX(-100%)',
  },
  dataTypeHeading: {
    fontSize: '1.6rem',
    fontWeight: 500,
    color: '#333',
  },
  dataTypeButton: {
    margin: theme.spacing(2, 0),
    fontSize: '1.2rem',
    textTransform: 'capitalize',
    '&:hover': {
      backgroundColor: '#f0f0f0',
    },
  },
  backButton: {
    display: 'flex',
    alignItems: 'center',
    textTransform: 'capitalize',
    '& h4': {
      fontSize: '0.8rem',
      fontWeight: 500,
      color: '#333',
    },
  },
  uploadHeading: {
    fontSize: '1.6rem',
    fontWeight: 500,
    color: '#333',
    marginBottom: theme.spacing(2),
  },
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
  }
}));

function Tool() {
  const [markers, setMarkers] = useState([]);
  const [expandTable, setExpandTable] = useState(false);
  const [selectedOption, setSelectedOption] = useState(null);
  const [showOptions, setShowOptions] = useState(true);
    // New state for transition effect
    const [checked, setChecked] = useState(false);

    const handleChange = () => {
      setChecked((prev) => !prev);
    };

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

  // keep your useStyles function as previously suggested

return (
  <div className={styles.toolContainer}>
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
        <div className={`${classes.sidebar}`}>
          <div className={styles.sidebarContent}>
            {showOptions ? (
              <div>
                <Typography variant="h4" className={classes.dataTypeHeading}>
                  Select your data type:
                </Typography>
                <Button variant="outlined" style={{marginTop: '1vh', marginLeft: "2vw", marginRight:"1vw"}} className={classes.dataTypeButton} onClick={() => handleOptionClick('fiber')}>
                  Fiber
                </Button>
                <Button variant="outlined" style={{marginTop: '1vh'}} className={classes.dataTypeButton} onClick={() => handleOptionClick('wireless')}>
                  Wireless
                </Button>
              </div>
            ) : (
              <div>
                <div className={classes.backButtonContainer}>
                  <Button variant="text" className={`${classes.backButton} ${styles.backButtonIcon}`} onClick={handleBack}>
                    <FontAwesomeIcon icon={faArrowLeft} className={styles.backButtonIcon} />
                    <Typography variant="h4">Go back</Typography>
                  </Button>
                </div>
                {selectedOption === 'fiber' && (
                  <div>
                    <Typography variant="h4" className={classes.uploadHeading}>
                      Fiber Upload Component
                    </Typography>
                    <Upload fetchMarkers={fetchMarkers} />
                  </div>
                )}
                {selectedOption === 'wireless' && (
                  <div>
                    <Typography variant="h4" className={classes.uploadHeading}>
                      Wireless Upload Component
                    </Typography>
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
