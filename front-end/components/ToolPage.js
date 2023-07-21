import React, { useState, useRef } from "react";
import Map from "./Map";
import Upload from "./Upload";
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
import Grow from '@mui/material/Grow';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import WifiIcon from '@mui/icons-material/Wifi';

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
  const [checked, setChecked] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleChange = () => {
    setChecked((prev) => !prev);
  };

  const classes = useStyles();
  const [tooltipOpen, setTooltipOpen] = useState(true);  // new state for tooltip

  const handleCloseTooltip = () => {   // new function to close tooltip
    setTooltipOpen(false);
  }

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
          <Map markers={markers} />
  );
}

export default Tool;