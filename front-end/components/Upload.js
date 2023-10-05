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
import Grid from "@mui/material/Grid";
import LoadingEffect from "./LoadingEffect";
import Swal from "sweetalert2";
import { Typography } from "@mui/material";
import { useRouter } from "next/router";
import { backend_url } from "../utils/settings";
import { styled } from "@mui/material/styles";
import styles from "../styles/Map.module.css";

import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

const StyledFormControl = styled(FormControl)({
  margin: "4px",
  minWidth: "150px",
  backgroundColor: "white",
  borderRadius: "4px",
  height: "25px",
  display: "flex",
  alignItems: "center",
});

const StyledSelect = styled(Select)({
  height: "25px",
  padding: "0 0 0 10px",
  minWidth: "150px",
});

const StyledTypography = styled(Typography)({
  marginTop: "20px",
  marginBottom: "20px",
});

const options = ["Fabric", "Network"];
const wiredWirelessOptions = {
  Wired: "Wired",
  Wireless: "Wireless",
};

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

const latency_type = {
  "<= 100 ms": 1,
  "> 100 ms": 0,
};

const bus_codes = {
  Business: "B",
  Residential: "R",
  Both: "X",
};

export default function Upload({ generateChallenge }) {
  const [open, setOpen] = React.useState(false);
  const anchorRef = React.useRef(null);
  const buttonGroupRef = React.useRef(null);
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const [downloadSpeed, setDownloadSpeed] = React.useState("");
  const [networkType, setNetworkType] = React.useState("");
  const [uploadSpeed, setUploadSpeed] = React.useState("");
  const [techType, setTechType] = React.useState("");
  const [latency, setLatency] = React.useState("");
  const [categoryCode, setCategoryCode] = React.useState("");
  const idCounterRef = React.useRef(1); // Counter for generating unique IDs
  const [exportSuccess, setExportSuccess] = React.useState(
    localStorage.getItem("exportSuccess") === "true" || false
  );
  const [buttonGroupWidth, setButtonGroupWidth] = React.useState(null);

  const [files, setFiles] = React.useState([]);

  const [isLoading, setIsLoading] = React.useState(false);
  const [isDataReady, setIsDataReady] = React.useState(false);
  const loadingTimeInMs = 3.5 * 60 * 1000;
  const router = useRouter();

  const handleChallengeClick = (event) => {
    event.preventDefault();

    const formData = new FormData();

    files.forEach((fileDetails) => {
      if (!fileDetails.file.name.toLowerCase().endsWith("kml")) {
        toast.error("Invalid File Format. Please upload a KML file.", {
          position: toast.POSITION.TOP_RIGHT,
          autoClose: 10000,
        });

        setIsLoading(false)
        return;
      }

      formData.append("fileData", JSON.stringify(fileDetails));
      formData.append("file", fileDetails.file);
    });

    setIsLoading(true);

    fetch(`${backend_url}/compute-challenge`, {
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
          // setIsLoading(false);
          return;
        } else if (response.status === 200) {
          return response.json();
        }
      })
      .catch((error) => {
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: "There is an error on our end, please try again later",
        });
        setIsLoading(false);
      });
  };

  const handleFilingClick = (event) => {
    event.preventDefault();

    const formData = new FormData();

    files.forEach((fileDetails) => {
      if (!fileDetails.file.name.toLowerCase().endsWith("kml")) {
        toast.error("Invalid File Format. Please upload a KML file.", {
          position: toast.POSITION.TOP_RIGHT,
          autoClose: 10000,
        });
        setIsLoading(false)

        return;
      }
      formData.append("fileData", JSON.stringify(fileDetails));
      formData.append("file", fileDetails.file);
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
        } else if (response.status === 200) {
          return response.json();
        } else if (response.status === 500 || response.status === 400) {
          setIsLoading(false);
          toast.error(
            "Invalid File Format, please upload file with supported format",
            {
              position: toast.POSITION.TOP_RIGHT,
              autoClose: 10000,
            }
          );
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
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: "There is an error on our end, please try again later",
        });
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
    const newFileDetails = Object.values(event.target.files).map((file) => ({
      id: idCounterRef.current++,
      name: file.name,
      option: options[selectedIndex],
      downloadSpeed: options[selectedIndex] === "Network" ? downloadSpeed : "",
      uploadSpeed: options[selectedIndex] === "Network" ? uploadSpeed : "",
      techType: options[selectedIndex] === "Network" ? techType : "",
      networkType: options[selectedIndex] === "Network" ? networkType : "",
      latency: options[selectedIndex] === "Network" ? latency : "",
      categoryCode: options[selectedIndex] === "Network" ? categoryCode : "",
      file: file,
    }));

    setFiles((prevFiles) => [...prevFiles, ...newFileDetails]);
  };

  const handleClick = () => {
    anchorRef.current.click();
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
    setFiles((prevFiles) =>
      prevFiles.filter((fileDetails) => fileDetails.id !== id)
    );
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
      field: "latency",
      headerName: "Latency",
      hide: selectedIndex !== 1, // Hide the column when "Network" is not selected
    },
    {
      field: "categoryCode",
      headerName: "Category",
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
      <ToastContainer />
      <div style={{ position: "fixed", zIndex: 10 }}>
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
                <label style={{ display: "block" }} htmlFor="downloadSpeed">
                  Download Speed:{" "}
                </label>
                <input
                  type="text"
                  id="downloadSpeed"
                  value={downloadSpeed}
                  onChange={(e) => setDownloadSpeed(e.target.value)}
                />
              </Grid>
              <Grid item xs={12} sm={2}>
                <label style={{ display: "block" }} htmlFor="uploadSpeed">
                  Upload Speed:{" "}
                </label>
                <input
                  type="text"
                  id="uploadSpeed"
                  value={uploadSpeed}
                  onChange={(e) => setUploadSpeed(e.target.value)}
                />
              </Grid>
              <Grid item xs={12} sm={2}>
                <label style={{ display: "block" }} htmlFor="techType">
                  Technology Type:{" "}
                </label>
                <StyledFormControl variant="outlined">
                  <StyledSelect
                    labelId="demo-simple-select-outlined-label"
                    id="demo-simple-select-outlined"
                    value={techType}
                    onChange={(e) => setTechType(e.target.value)}
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
                  </StyledSelect>
                </StyledFormControl>
              </Grid>
              <Grid item xs={12} sm={2}>
                <label style={{ display: "block" }} htmlFor="wiredWireless">
                  Network Type:{" "}
                </label>
                <StyledFormControl variant="outlined">
                  <StyledSelect
                    labelId="demo-simple-select-outlined-label"
                    id="demo-simple-select-outlined"
                    value={networkType}
                    onChange={(e) => setNetworkType(e.target.value)}
                  >
                    {Object.entries(wiredWirelessOptions).map(
                      ([key, value]) => (
                        <MenuItem key={value} value={value}>
                          {key}
                        </MenuItem>
                      )
                    )}
                  </StyledSelect>
                </StyledFormControl>
              </Grid>{" "}
              <Grid item xs={12} sm={2}>
                <label style={{ display: "block" }} htmlFor="techType">
                  Latency:{" "}
                </label>
                <StyledFormControl variant="outlined">
                  <StyledSelect
                    labelId="demo-simple-select-outlined-label"
                    id="demo-simple-select-outlined"
                    value={latency}
                    onChange={(e) => setLatency(e.target.value)}
                  >
                    {Object.entries(latency_type).map(([key, value]) => (
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
                  </StyledSelect>
                </StyledFormControl>
              </Grid>
              <Grid item xs={12} sm={2}>
                <label style={{ display: "block" }} htmlFor="techType">
                  Category:{" "}
                </label>
                <StyledFormControl variant="outlined">
                  <StyledSelect
                    labelId="demo-simple-select-outlined-label"
                    id="demo-simple-select-outlined"
                    value={categoryCode}
                    onChange={(e) => setCategoryCode(e.target.value)}
                  >
                    {Object.entries(bus_codes).map(([key, value]) => (
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
                  </StyledSelect>
                </StyledFormControl>
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
            rows={files}
            columns={columns}
            pageSize={5}
            checkboxSelection
          />
        </Box>
        {!generateChallenge && (
          <Box sx={{ display: "flex", marginTop: "1rem", gap: "1rem" }}>
            <ExportButton
              onClick={handleFilingClick}
              challenge={generateChallenge}
            />
          </Box>
        )}
        {generateChallenge && (
          <Box sx={{ display: "flex", marginTop: "1rem", gap: "1rem" }}>
            <ExportButton
              onClick={handleChallengeClick}
              challenge={generateChallenge}
            />
          </Box>
        )}
      </Box>
    </React.Fragment>
  );
}
