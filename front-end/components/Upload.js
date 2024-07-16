import * as React from "react";
import ButtonGroup from "@mui/material/ButtonGroup";
import ArrowDropDownIcon from "@mui/icons-material/ArrowDropDown";
import ClickAwayListener from "@mui/material/ClickAwayListener";
import Grow from "@mui/material/Grow";
import Paper from "@mui/material/Paper";
import Popper from "@mui/material/Popper";
import MenuList from "@mui/material/MenuList";
import Tooltip from "@mui/material/Tooltip";
import Input from "@mui/material/Input";
import ExportButton from "./SubmitButton";
import { DataGrid } from "@mui/x-data-grid";
import { FormControl, InputLabel, MenuItem, Select, Button, Dialog, DialogActions, DialogTitle, DialogContent, Box } from '@mui/material';
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
import { useFolder } from '../contexts/FolderContext';
import { format } from "date-fns";



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

const StyledInput = styled(Input)({
  padding: '10px',
  margin: '4px',
  border: '1px solid #ccc',
  borderRadius: '4px',
  width: 'calc(100% - 24px)', // accounting for padding and margins
  boxSizing: 'border-box', // make sure padding doesn't affect the width
  maxHeight: '30%'
});

const StyledGridItem = styled(Grid)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'flex-start', // Align items to the start of the flex container
  alignItems: 'flex-start', // Align items to the start of the cross axis
  padding: theme.spacing(1),
  [theme.breakpoints.down('xs')]: {
    width: '100%',
    boxSizing: 'border-box',
  },
}));

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
  "Other": 0,
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

export default function Upload() {
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

  const [files, setFiles] = React.useState([]);

  const [isLoading, setIsLoading] = React.useState(false);
  const [isDataReady, setIsDataReady] = React.useState(false);
  const loadingTimeInMs = 3.5 * 60 * 1000;
  const router = useRouter();

  const { folderID, setFolderID } = useFolder();
  const [folders, setFolders] = React.useState([]);

  const [newDeadline, setNewDeadline] = React.useState({ month: '', year: '' });

  const [importFolderID, setImportFolderID] = React.useState(-1);

  const months = Array.from({ length: 12 }, (_, i) => i + 1); // Months 1-12
  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: 10 }, (_, i) => currentYear - 5 + i);



  const fetchFolders = async () => {
    try {
      const response = await fetch(`${backend_url}/api/folders-with-deadlines`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      });

      if (response.status === 401) {
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: "Session expired, please log in again!",
        });
        router.push("/login");
        return;
      }

      const data = await response.json();
      setFolders(data);

    } catch (error) {
      console.error("Error fetching folders:", error);
    }
  };


  const handleFilingClick = (event) => {
    event.preventDefault();

    const formData = new FormData();
    formData.append("deadline", `${newDeadline.year}-${newDeadline.month}-03`);
    formData.append("importFolder", importFolderID);
    files.forEach((fileDetails) => {
      const allowedExtensions = ["kml", "geojson", "csv"];
      const fileExtension = fileDetails.file.name
        .split(".")
        .pop()
        .toLowerCase();

      if (!allowedExtensions.includes(fileExtension)) {
        toast.error(
          "Invalid File Format. Please upload a KML, GeoJSON, or CSV file.",
          {
            position: toast.POSITION.TOP_RIGHT,
            autoClose: 10000,
          }
        );

        setIsLoading(false);
        return;
      }
      formData.append("fileData", JSON.stringify(fileDetails));
      formData.append("file", fileDetails.file);
    });

    setIsLoading(true);

    fetch(`${backend_url}/api/submit-data/${folderID}`, {
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
            fetch(`${backend_url}/api/status/${data.task_id}`)
              .then((response) => response.json())
              .then((status) => {
                if (status.state !== "PENDING") {
                  clearInterval(intervalId);
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

  React.useEffect(() => {
    fetchFolders();
  }, []);

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

    // Reset the file input element
    const fileInput = anchorRef.current;
    if (fileInput) {
      fileInput.value = "";
    }
  };

  const handleDeadlineSelect = (newFolderID) => {
    if (newFolderID === folderID) {
      return;
    }
    if (newFolderID === -1) {
      // Reset deadline selection
      setNewDeadline({ month: '', year: '' });
    }
    else {
      const selectedFolder = folders.find(folder => folder.folder_id === newFolderID);
      if (selectedFolder) {
        // Parse the deadline date of the selected folder
        const date = new Date(selectedFolder.deadline);
        const month = date.getMonth() + 1;  // getMonth() is zero-indexed, so add 1
        const year = date.getFullYear();
        // Set newDeadline to reflect the selected folder's deadline
        setNewDeadline({ month: month.toString(), year: year.toString() });
      }
    }
    setFolderID(newFolderID);
  };

  const handleImportChange = (event) => {
    const selectedFolderID = event.target.value;
    setImportFolderID(selectedFolderID);

  };

  const handleNewDeadlineChange = ({ month, year }) => {

    setNewDeadline({ month, year });

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
        <div>
          <FormControl style={{ width: '300px', marginBottom: '20px' }}>
            <InputLabel id="filing-select-label">You are working on filing for deadline:</InputLabel>
            <Select
              labelId="filing-select-label"
              id="filing-select"
              value={folderID}
              label="You are working on Filing for Deadline:"
              onChange={(e) => handleDeadlineSelect(e.target.value)}
            >
              <MenuItem value={-1}><em>Create New Filing for Deadline:</em></MenuItem>
              {folders.map((folder) => (
                <MenuItem key={folder.deadline} value={folder.folder_id}>
                  {format(new Date(folder.deadline), 'MMMM yyyy')}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {folderID === -1 && (
            <>
              <FormControl style={{ width: '120px' }}>
                <InputLabel id="month-select-label">Month</InputLabel>
                <Select
                  labelId="month-select-label"
                  id="month-select"
                  value={newDeadline.month}
                  label="Month"
                  onChange={e => handleNewDeadlineChange({ ...newDeadline, month: e.target.value })}
                >
                  {months.map(month => (
                    <MenuItem key={month} value={month}>{month}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl style={{ width: '120px', marginRight: '20px' }}>
                <InputLabel id="year-select-label">Year</InputLabel>
                <Select
                  labelId="year-select-label"
                  id="year-select"
                  value={newDeadline.year}
                  label="Year"
                  onChange={e => handleNewDeadlineChange({ ...newDeadline, year: e.target.value })}
                >
                  {years.map(year => (
                    <MenuItem key={year} value={year}>{year}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl style={{ width: '300px', border: '1px solid #78fff1' }}>
                <InputLabel id="import-select-label">Import Data from Previous Filing</InputLabel>
                <Select
                  labelId="import-select-label"
                  id="import-select"
                  value={importFolderID}
                  onChange={handleImportChange}
                >
                  <MenuItem value={-1}>
                    <em>Don't Import</em>
                  </MenuItem>
                  {folders.map(folder => (
                    <MenuItem key={folder.folder_id} value={folder.folder_id}>
                      {format(new Date(folder.deadline), 'MMMM yyyy')}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </>
          )}
        </div>
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
              <Paper>
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
              <StyledGridItem item xs={12} sm={2}>
                <label style={{ display: "block" }} htmlFor="downloadSpeed">
                  Download Speed(Mbps):{" "}
                </label>
                <StyledInput
                  type="text"
                  id="downloadSpeed"
                  value={downloadSpeed}
                  onChange={(e) => setDownloadSpeed(e.target.value)}
                />
              </StyledGridItem>
              <StyledGridItem item xs={12} sm={2}>
                <label style={{ display: "block" }} htmlFor="uploadSpeed">
                  Upload Speed(Mbps):{" "}
                </label>
                <StyledInput
                  type="text"
                  id="uploadSpeed"
                  value={uploadSpeed}
                  onChange={(e) => setUploadSpeed(e.target.value)}
                />
              </StyledGridItem>
              <StyledGridItem item xs={12} sm={2}>
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
                        <Tooltip title={key} placement="right">
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
                        </Tooltip>
                      </MenuItem>
                    ))}
                  </StyledSelect>
                </StyledFormControl>
              </StyledGridItem>
              <StyledGridItem item xs={12} sm={2}>
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
              </StyledGridItem>
              <StyledGridItem item xs={12} sm={2}>
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
              </StyledGridItem>
              <StyledGridItem item xs={12} sm={2}>
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
              </StyledGridItem>
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
        <Box sx={{ display: "flex", marginTop: "1rem", gap: "1rem" }}>
          <ExportButton
            onClick={handleFilingClick}
          />
        </Box>
      </Box>
    </React.Fragment>
  );
}
