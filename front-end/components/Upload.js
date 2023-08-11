import * as React from "react";
import Button from "@mui/material/Button";
import ButtonGroup from "@mui/material/ButtonGroup";
import ArrowDropDownIcon from "@mui/icons-material/ArrowDropDown";
import ClickAwayListener from "@mui/material/ClickAwayListener";
import Grow from "@mui/material/Grow";
import Paper from "@mui/material/Paper";
import Popper from "@mui/material/Popper";
import MenuItem from "@mui/material/MenuItem";
import MenuList from "@mui/material/MenuList";
import Box from "@mui/material/Box";
import ExportButton from "./SubmitButton";
import { DataGrid } from "@mui/x-data-grid";
import Select from "@mui/material/Select";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import Grid from "@mui/material/Grid";
import LoadingEffect from "./LoadingEffect";
import Swal from "sweetalert2";
import { makeStyles, TextField, Typography } from "@material-ui/core";
import { useRouter } from "next/router";
import { backend_url } from "../utils/settings";

// Define your styles
const useStyles = makeStyles((theme) => ({
  buttonGroup: {
    color: "#FFF",
    backgroundColor: "#3f51b5",
    padding: "10px 20px",
    borderRadius: "5px",
    margin: "10px 0",
  },
  paper: {
    backgroundColor: "#f3f3f3",
    padding: "10px",
    borderRadius: "5px",
  },
  formControl: {
    margin: "4px",
    minWidth: "150px",
    backgroundColor: "white",
    borderRadius: "4px",
    height: "25px",
    display: "flex",
    alignItems: "center",
  },
  inputLabel: {
    fontSize: "0.875rem",
    top: "-000px",
  },
  select: {
    height: "25px",
    padding: "0 0 0 10px",
    minWidth: "150px",
  },
  gridItem: {
    padding: "10px",
  },
  headertext: {
    marginTop: "20px",
    marginBottom: "20px",
  },
}));

const options = ["Fabric", "Network"];
const wiredWirelessOptions = {
  Wired: "Wired",
  Wireless: "Wireless",
};
let storage = [];
let storage2 = [];

const tech_types = {
  "Copper Wire": 10,
  "Coaxial Cable / HFC": 40,
  "Optical Carrier / Fiber to the Premises": 50,
  "Geostationary Satellite": 60,
  "Non-geostationary Satellite": 61,
  "Unlicensed Terrestrial Fixed Wireless": 70,
  "Licensed Terrestrial Fixed Wireless": 71,
  "Licensed-by-Rule Terrestrial Fixed Wireless": 72,
  Other: 0,
};

function MapKey() {
  return (
    <div style={{ display: "flex", alignItems: "center" }}>
      <span
        style={{
          height: "10px",
          width: "10px",
          backgroundColor: "Green",
          display: "inline-block",
          marginRight: "5px",
        }}
      ></span>
      <span style={{ marginRight: "15px" }}>Served</span>
      <span
        style={{
          height: "10px",
          width: "10px",
          backgroundColor: "Red",
          display: "inline-block",
          marginRight: "5px",
        }}
      ></span>
      <span>Unserved</span>
    </div>
  );
}

export default function Upload({ fetchMarkers }) {
  const classes = useStyles();
  const [open, setOpen] = React.useState(false);
  const anchorRef = React.useRef(null);
  const buttonGroupRef = React.useRef(null);
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const [selectedFiles, setSelectedFiles] = React.useState([]
  );
  const [downloadSpeed, setDownloadSpeed] = React.useState("");
  const [networkType, setNetworkType] = React.useState("");
  const [uploadSpeed, setUploadSpeed] = React.useState("");
  const [techType, setTechType] = React.useState("");
  const idCounterRef = React.useRef(1); // Counter for generating unique IDs
  const [exportSuccess, setExportSuccess] = React.useState(
    localStorage.getItem("exportSuccess") === "true" || false
  );
  const [buttonGroupWidth, setButtonGroupWidth] = React.useState(null);

  const [isLoading, setIsLoading] = React.useState(false);
  const [isDataReady, setIsDataReady] = React.useState(false);
  const loadingTimeInMs = 3.5 * 60 * 1000;
  const router = useRouter();

  const handleExportClick = (event) => {
    event.preventDefault();

    const formData = new FormData();

    storage2.forEach((file) => {
      const fileObj = file[0];
      const newFile = file[1];

      formData.append("fileData", JSON.stringify(newFile));
      formData.append("file", fileObj);
    });

    setIsLoading(true);

    fetch(`${backend_url}/submit-data`, {
      method: "POST",
      body: formData,
      credentials: "include",
    })
      .then((response) => {
        if (response.status === 401) {
          Swal.fire({
            icon: "error",
            title: "Oops...",
            text: "Session expired, please log in again!",
          });
          // Redirect to login page
          router.push("/login");
          setIsLoading(false);
          return;
        }
        else if (response.status === 200) {
          return response.json();
        }
      })
      .then((data) => {
        if (data) {
          const intervalId = setInterval(() => {
            console.log(data.task_id);
            fetch(`${backend_url}/status/${data.task_id}`)
              .then((response) => response.json())
              .then((status) => {
                if (status.state !== "PENDING") {
                  clearInterval(intervalId);
                  setExportSuccess(true);
                  setIsDataReady(true);
                  setIsLoading(false);
                  setTimeout(() => {
                    setIsDataReady(false);
                    router.reload();
                  }, 5000);
                }
              });
          }, 5000);
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        setIsLoading(false);
      });
  };

  // Call fetchMarkers when the Export button is clicked
  React.useEffect(() => {
    if (exportSuccess) {
      const dynamicMap = document.getElementById("dynamic-map");
      if (dynamicMap) {
        dynamicMap.fetchMarkers(); // Call fetchMarkers function in the DynamicMap component
      }
    }
    if (buttonGroupRef.current) {
      setButtonGroupWidth(buttonGroupRef.current.offsetWidth);
    }
  }, [exportSuccess, buttonGroupRef]);

  const handleFileChange = (event) => {
    const newFiles = Object.values(event.target.files).map((file) => ({
      id: idCounterRef.current++,
      name: file.name,
      option: options[selectedIndex], // Track the selected option for each file
      downloadSpeed: options[selectedIndex] === "Network" ? downloadSpeed : "",
      uploadSpeed: options[selectedIndex] === "Network" ? uploadSpeed : "",
      techType: options[selectedIndex] === "Network" ? techType : "",
      networkType: options[selectedIndex] === "Network" ? networkType : "",
    }));

    const newFile = {
      id: idCounterRef.current,
      name: event.target.files[0].name,
      option: options[selectedIndex],
      downloadSpeed: options[selectedIndex] === "Network" ? downloadSpeed : "",
      uploadSpeed: options[selectedIndex] === "Network" ? uploadSpeed : "",
      techType: options[selectedIndex] === "Network" ? techType : "",
      networkType: options[selectedIndex] === "Network" ? networkType : "",
    };
    storage2.push([event.target.files[0], newFile]);
    storage.push([event.target.files[0], newFiles]);

    const updatedFiles = [...selectedFiles, ...newFiles];
    setSelectedFiles(updatedFiles);
    // localStorage.setItem("storage", JSON.stringify(storage)); // update local storage for storage array
  };

  const handleClick = () => {
    console.info(`You clicked ${options[selectedIndex]}`);
    anchorRef.current.click();
    console.log(storage.length)
  };

  const handleMenuItemClick = (event, index) => {
    setSelectedIndex(index);
    setOpen(false);
  };

  const handleToggle = () => {
    setOpen((prevOpen) => !prevOpen);
  };

  const handleClose = (event) => {
    if (anchorRef.current && anchorRef.current.contains(event.target)) {
      return;
    }

    setOpen(false);
  };

  const handleDelete = (id) => {
    // Iterate through the 'storage' array and remove the matching file
    for (let i = 0; i < storage.length; i++) {
      if (storage[i][1] === id) {
        storage.splice(i, 1);
        // localStorage.setItem("storage", JSON.stringify(storage)); // update local storage for storage array
        break;
      }
    }

    // Update selectedFiles state
    setSelectedFiles((prevFiles) => prevFiles.filter((file) => file.id !== id));
    setExportSuccess(false); // Set the export success state to true

    // Reset the file input element
    const fileInput = anchorRef.current;
    if (fileInput) {
      fileInput.value = "";
    }
  };

  const columns = [
    { field: "id", headerName: "ID" },
    {
      field: "name",
      headerName: "File Name",
      editable: true,
    },
    {
      field: "option",
      headerName: "Option",
    },
    {
      field: "downloadSpeed",
      headerName: "Download Speed",
      hide: selectedIndex !== 1, // Hide the column when "Network" is not selected
    },
    {
      field: "uploadSpeed",
      headerName: "Upload Speed",
      hide: selectedIndex !== 1, // Hide the column when "Network" is not selected
    },
    {
      field: "techType",
      headerName: "Tech Type",
      hide: selectedIndex !== 1, // Hide the column when "Network" is not selected
    },
    {
      field: "networkType",
      headerName: "Network Type",
      hide: selectedIndex !== 1, // Hide the column when "Network" is not selected
    },
    {
      field: "actions",
      headerName: "Actions",
      renderCell: (params) => (
        <Button
          onClick={() => handleDelete(params.row.id)}
          color="error"
          variant="outlined"
          size="small"
        >
          Delete
        </Button>
      ),
    },
  ];

  React.useEffect(() => {
    // Store the exportSuccess state in local storage whenever it changes
    localStorage.setItem("exportSuccess", exportSuccess);
  }, [exportSuccess]);

  return (
    <React.Fragment>
      <div style={{ position: 'fixed', zIndex: 10000 }}>
      {(isLoading || isDataReady) && (
        <LoadingEffect
          isLoading={isLoading}
          loadingTimeInMs={loadingTimeInMs}
        />
      )}
      </div>
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-end", // This line
          marginLeft: "20px",
          zIndex: 1000,
          position: "relative",
        }}
      >
        <Typography component="h1" variant="h5" className={classes.headertext}>
          Upload Network Files Below:
        </Typography>

        <ButtonGroup
          variant="contained"
          ref={buttonGroupRef}
          style={{ width: "fit-content" }} // Add this line
        >
          <Button onClick={handleClick}>{options[selectedIndex]}</Button>
          <Button
            size="small"
            aria-controls={open ? "split-button-menu" : undefined}
            aria-expanded={open ? "true" : undefined}
            aria-label="select merge strategy"
            aria-haspopup="menu"
            onClick={handleToggle}
          >
            <ArrowDropDownIcon />
          </Button>
        </ButtonGroup>
        <Popper
          sx={{
            zIndex: 1,
          }}
          open={open}
          anchorEl={buttonGroupRef.current}
          role={undefined}
          transition
          disablePortal
        >
          {({ TransitionProps, placement }) => (
            <Grow
              {...TransitionProps}
              style={{
                transformOrigin:
                  placement === "bottom" ? "center top" : "center bottom",
              }}
            >
              <Paper style={{ width: buttonGroupWidth }}>
                <ClickAwayListener onClickAway={handleClose}>
                  <MenuList id="split-button-menu" autoFocusItem>
                    {options.map((option, index) => (
                      <MenuItem
                        key={option}
                        selected={index === selectedIndex}
                        onClick={(event) => handleMenuItemClick(event, index)}
                      >
                        {option}
                      </MenuItem>
                    ))}
                  </MenuList>
                </ClickAwayListener>
              </Paper>
            </Grow>
          )}
        </Popper>
        {selectedIndex === 1 && (
          <Box sx={{ marginTop: "1rem" }}>
            <Grid container spacing={1}>
              <Grid item xs={12} sm={2}>
                <label htmlFor="downloadSpeed">Download Speed (MBps): </label>
                <input
                  type="text"
                  id="downloadSpeed"
                  value={downloadSpeed}
                  onChange={(e) => setDownloadSpeed(e.target.value)}
                />
              </Grid>
              <Grid item xs={12} sm={2}>
                <label htmlFor="uploadSpeed">Upload Speed (MBps): </label>
                <input
                  type="text"
                  id="uploadSpeed"
                  value={uploadSpeed}
                  onChange={(e) => setUploadSpeed(e.target.value)}
                />
              </Grid>
              <Grid item xs={12} sm={2}>
                <label htmlFor="techType">Technology Type: </label>
                <FormControl variant="outlined" className={classes.formControl}>
                  <Select
                    labelId="demo-simple-select-outlined-label"
                    id="demo-simple-select-outlined"
                    value={techType}
                    onChange={(e) => setTechType(e.target.value)}
                    className={classes.select}
                  >
                    {Object.entries(tech_types).map(([key, value]) => (
                      <MenuItem key={value} value={value}>
                        <div
                          style={{
                            maxWidth: techType === value ? "100px" : "none",
                            textOverflow:
                              techType === value ? "ellipsis" : "initial",
                            overflow: techType === value ? "hidden" : "initial",
                            whiteSpace:
                              techType === value ? "nowrap" : "initial",
                          }}
                        >
                          {key}
                        </div>
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={2}>
                <label htmlFor="wiredWireless">Network Type: </label>
                <FormControl variant="outlined" className={classes.formControl}>
                  <Select
                    labelId="demo-simple-select-outlined-label"
                    id="demo-simple-select-outlined"
                    value={networkType}
                    onChange={(e) => setNetworkType(e.target.value)}
                    className={classes.select}
                  >
                    {Object.entries(wiredWirelessOptions).map(
                      ([key, value]) => (
                        <MenuItem key={value} value={value}>
                          {key}
                        </MenuItem>
                      )
                    )}
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          </Box>
        )}
        {/* Hidden file input to allow file selection */}
        <input
          type="file"
          style={{ display: "none" }}
          onChange={handleFileChange}
          ref={anchorRef}
        />
        {/* Display the uploaded files in a DataGrid */}
        <Box sx={{ height: 400 }} style={{ marginTop: "3vh" }}>
          <DataGrid
            rows={selectedFiles}
            columns={columns}
            pageSize={5}
            checkboxSelection
          />
        </Box>
        <Box sx={{ display: "flex", marginTop: "1rem", gap: "1rem" }}>
          <ExportButton onClick={handleExportClick} />
          <MapKey />
        </Box>
      </Box>
    </React.Fragment>
  );
}