import React, { useState } from 'react';
import Navbar from '../components/Navbar';
import SmallLoadingEffect from '../components/SmallLoadingEffect';
import WirelessCoveragemap from '../components/WirelessCoveragemap';
import { useRouter } from "next/router";
import { backend_url } from '../utils/settings';
import {
  Typography,
  Container,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Grid,
  Paper,
  Drawer,
  Tooltip,
  Input,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from '@mui/material';
import Swal from 'sweetalert2';
import { styled } from "@mui/material/styles";


const fieldGroups = {
  towerLocation: [
    { key: 'towername', label: 'Tower Name', unit: '' },
    { key: 'latitude', label: 'Latitude', unit: 'degrees' },
    { key: 'longitude', label: 'Longitude', unit: 'degrees' },
    // ... other tower location fields
  ],
  signalStrength: [
    // { key: 'erp', label: 'Effective Radiated Power', unit: 'dBd' },
    { key: 'frequency', label: 'Frequency', unit: 'MHz' },
    { key: 'radius', label: 'Coverage Radius', unit: 'Km' },
    // ... other signal strength fields
  ],
  antennaInformation: [
    { key: 'antennaHeight', label: 'Antenna Height', unit: 'meters' },
    { key: 'antennaTilt', label: 'Antenna Tilt', unit: 'degrees' },
    { key: 'horizontalFacing', label: 'Horizontal Facing', unit: 'degrees' },
    { key: 'effectiveRadPower', label: 'Effective Radiated Power', unit: 'dBd'},
    { key: 'downtilt', label: 'Downtilt', unit: 'degrees'},
    { key: 'downtiltDirection', label: 'Downtilt Direction', unit: 'degrees'}
    // ... other antenna information fields
  ],
  filterOptions: [
    { key: 'floorLossRate', label: 'Floor Loss Rate', unit: 'dB' },
    // ... other filter option fields if needed
  ],
};

const formContainerStyle = {
  maxHeight: 'calc(100vh)',
  overflowY: 'auto',
};


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

const networkInfoHeaderStyle = {
  textAlign: 'center',
  margin: '10px 0',
  fontWeight: 'bold',
};

const tech_types = {
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

const StyledInput = styled(Input)({
  padding: '10px',
  margin: '4px',
  border: '1px solid #ccc',
  borderRadius: '4px',
  width: 'calc(100% - 24px)', // accounting for padding and margins
  boxSizing: 'border-box', // make sure padding doesn't affect the width
  maxHeight: '30%'
});

const StyledButton = styled(Button)({
  margin: '20px 4px 4px',
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

const WirelessExtension = () => {

  const [isLoadingForUntimedEffect, setIsLoadingForUntimedEffect] = useState(false);
  const [formData, setFormData] = useState({
    towername: '',
    latitude: '',
    longitude: '',
    frequency: '',
    radius: '',
    antennaHeight: '',
    antennaTilt: '',
    horizontalFacing: '',
    floorLossRate: 150,
    effectiveRadPower: '',
    downtilt: '',
    downtiltDirection: ''

    // ... include other default values as necessary
  });
  const [inPreviewMode, setInPreviewMode] = useState(false);
  const [colorMapping, setColorMapping] = useState({});
  const [saveCoverage, setSaveCoverage] = useState(false);

  const [imageUrl, setImageUrl] = useState(''); 
  const [transparentImageUrl, setTransparentImageUrl] = useState('');
  const [bounds, setBounds] = useState({
    north: 39.5, east: -98.5, south: 39.5, west: -98.5
  });

  const [downloadSpeed, setDownloadSpeed] = React.useState("");
  const [uploadSpeed, setUploadSpeed] = React.useState("");
  const [techType, setTechType] = React.useState("");
  const [latency, setLatency] = React.useState("");
  const [categoryCode, setCategoryCode] = React.useState("");

  const [openDialog, setOpenDialog] = useState(false);


  const router = useRouter();
  const handleDialogClose = (option) => {
    setOpenDialog(false);
    if (option === 'mainPage') {
      router.push('/');
    }
  };

  const handleInputChange = (event) => {
    const { name, value } = event.target;
    setFormData((prevFormData) => ({
      ...prevFormData,
      [name]: value,
    }));
  };

  const fetchKMLFile = (kml_filename) => {
    fetch(`${backend_url}/api/download-kmlfile/${kml_filename}`, {
      method: "GET",
      credentials: "include", // make sure to send credentials to maintain the session
    })
      .then((response) => {
        if (response.ok) {
          return response.blob();
        } else {
          throw new Error('Failed to fetch file');
        }
      })
      .then((blob) => {
        // Create a URL for the blob
        const fileUrl = URL.createObjectURL(blob);

        // Create a temporary anchor element and trigger a download
        const a = document.createElement("a");
        a.href = fileUrl;
        a.download = kml_filename; // Set the file name for download
        document.body.appendChild(a); // Append to the document
        a.click(); // Trigger a click to download

        // Clean up: remove the anchor element and revoke the object URL
        document.body.removeChild(a);
        URL.revokeObjectURL(fileUrl);
      })
      .catch((error) => {
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: error.message,
        });
      });
  };

  const fetchRasterImage = (towerId) => {
    fetch(`${backend_url}/api/get-raster-image/${towerId}`, {
      method: "GET",
      credentials: "include", // make sure to send credentials to maintain the session
    })
      .then((response) => {
        if (response.ok) {
          return response.blob().then(imageBlob => ({
            imageBlob
          }));
        } else {
          throw new Error('Failed to fetch raster data');
        }
      })
      .then(({ imageBlob }) => {
        // Create a URL for the image blob
        const imageUrl = URL.createObjectURL(imageBlob);
        setImageUrl(imageUrl);
      })
      .catch((error) => {
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: error.message,
        });
      });
  };

  const fetchTransparentRasterImage = (towerId) => {
    fetch(`${backend_url}/api/get-transparent-raster-image/${towerId}`, {
      method: "GET",
      credentials: "include", // make sure to send credentials to maintain the session
    })
      .then((response) => {
        if (response.ok) {
          return response.blob().then(imageBlob => ({
            imageBlob
          }));
        } else {
          throw new Error('Failed to fetch raster data');
        }
      })
      .then(({ imageBlob }) => {
        // Create a URL for the image blob
        const imageUrl = URL.createObjectURL(imageBlob);
        setTransparentImageUrl(imageUrl);
      })
      .catch((error) => {
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: error.message,
        });
      });
  };

  const fetchRasterBounds = (towerId) => {
    fetch(`${backend_url}/api/get-raster-bounds/${towerId}`, {
      method: "GET",
      credentials: "include", // make sure to send credentials to maintain the session
    })
      .then((response) => {
        if (response.ok) {
          return response.json(); // Parse the JSON response body
        } else {
          throw new Error('Failed to fetch raster bounds');
        }
      })
      .then((data) => {
        // Use the bounds from the response data
        setBounds(data.bounds);
      })
      .catch((error) => {
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: error.message,
        });
      });
  };

  const fetchLossToColorMapping = (towerId) => {
    fetch(`${backend_url}/api/get-loss-color-mapping/${towerId}`, {
      method: "GET",
      credentials: "include",
    })
      .then((response) => {
        if (response.ok) {
          return response.json();
        } else {
          throw new Error('Failed to fetch loss to color mapping');
        }
      })
      .then((mapping) => {
        setColorMapping(mapping); // Update the state with the fetched mapping
      })
      .catch((error) => {
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: error.message,
        });
      });
  };

  const handleComputeCoverage = (event) => {
    event.preventDefault();
    setIsLoadingForUntimedEffect(true);
    fetch(`${backend_url}/api/compute-wireless-coverage`, {
      method: "POST",
      headers: {
        'Content-Type': 'application/json', // Set the content type to application/json
      },
      body: JSON.stringify(formData), // Serialize formData to JSON
      credentials: "include",
    })
      .then((response) => {
        if (response.status === 401) {
          setIsLoadingForUntimedEffect(false);
          Swal.fire({
            icon: "error",
            title: "Oops...",
            text: "Session expired, please log in again!",
          });
          // Redirect to login page
          router.push("/login");
          return;
        } else if (response.status === 200) {
          setInPreviewMode(true);
          return response.json();
        } else if (response.status === 500 || response.status === 400) {
          setIsLoadingForUntimedEffect(false);
          toast.error(
            "There is an error on our end",
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
            fetch(`${backend_url}/status/${data.task_id}`)
              .then((response) => response.json())
              .then((status) => {
                if (status.state !== "PENDING") {
                  setIsLoadingForUntimedEffect(false);
                  clearInterval(intervalId);
                  fetchRasterImage(formData.towername);
                  fetchTransparentRasterImage(formData.towername);
                  fetchRasterBounds(formData.towername);
                  fetchLossToColorMapping(formData.towername);
                }
              });
          }, 5000);
        }
      })
      .catch((error) => {
        setIsLoadingForUntimedEffect(false);
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: "There is an error on our end, please try again later",
        });
        console.error("Error:", error);

      });
  };

  const saveCoverageClick = (event) => {
    event.preventDefault();
    setSaveCoverage(true);
  };

  const handleSaveCoverage = (event) => {
    event.preventDefault();
    setIsLoadingForUntimedEffect(true);
    const coverageData = {
      towername: formData.towername, // Ensure towername is included
      downloadSpeed: downloadSpeed,
      uploadSpeed: uploadSpeed,
      techType: techType,
      latency: latency,
      categoryCode: categoryCode
    };
    console.log(coverageData);
    fetch(`${backend_url}/api/compute-wireless-prediction-fabric-coverage`, {
      method: "POST",
      headers: {
        'Content-Type': 'application/json', // Set the content type to application/json
      },
      body: JSON.stringify(coverageData), // Serialize formData to JSON
      credentials: "include",
    })
      .then((response) => {
        if (response.status === 401) {
          setIsLoadingForUntimedEffect(false);
          Swal.fire({
            icon: "error",
            title: "Oops...",
            text: "Session expired, please log in again!",
          });
          // Redirect to login page
          router.push("/login");
          return;
        } else if (response.status === 200) {
          return response.json();
        } else if (response.status === 500 || response.status === 400) {
          setIsLoadingForUntimedEffect(false);
          toast.error(
            "There is an error on our end",
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
            fetch(`${backend_url}/status/${data.task_id}`)
              .then((response) => response.json())
              .then((status) => {
                if (status.state !== "PENDING") {
                  setIsLoadingForUntimedEffect(false);
                  clearInterval(intervalId);
                  setSaveCoverage(false);
                  fetchKMLFile(data.kml_filename);
                  setOpenDialog(true);
                }
              });
          }, 5000);
        }
      })
      .catch((error) => {
        setIsLoadingForUntimedEffect(false);
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: "There is an error on our end, please try again later",
        });
        console.error("Error:", error);

      });
  };

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      // setIsLoadingForUntimedEffect(true);
      const formD = new FormData();
      formD.append('file', file);

      fetch(`${backend_url}/api/upload-tower-csv`, {
        method: 'POST',
        credentials: 'include',
        body: formD
      })
        .then((response) => {
          if (response.status === 401) {
            setIsLoadingForUntimedEffect(false);
            Swal.fire({
              icon: "error",
              title: "Oops...",
              text: "Session expired, please log in again!",
            });
            // Redirect to login page
            router.push("/login");
            return;
          } else if (response.status === 200) {
            return response.json();
          } else if (response.status === 500 || response.status === 400) {
            setIsLoadingForUntimedEffect(false);
            toast.error(
              "There is an error on our end",
              {
                position: toast.POSITION.TOP_RIGHT,
                autoClose: 10000,
              }
            );
          }
        })
        .then(data => {
          // Assuming the backend returns the parsed CSV data in the same structure as the formData state

          // The backend returns an array with a dict object for each tower, since we only support
          // single tower information in the frontend, we just use data[0] for now.

          setFormData(prevFormData => ({
            ...prevFormData,
            towername: data[0].towerName || '',
            latitude: data[0].latitude || '',
            longitude: data[0].longitude || '',
            frequency: data[0].frequency || '',
            radius: data[0].coverageRadius || '',
            antennaHeight: data[0].antennaHeight || '',
            antennaTilt: data[0].antennaTilt || '',
            horizontalFacing: data[0].horizontalFacing || '',
            floorLossRate: data[0].floorLossRate || 150,
            effectiveRadPower: data[0].effectiveRadPower || '',
            downtilt: data[0].downtilt || '',
            downtiltDirection: data[0].downtilt || ''
          }));
        })
        .catch(error => {
          // setIsLoadingForUntimedEffect(false);
          Swal.fire({
            icon: "error",
            title: "Oops...",
            text: "There was a problem uploading the file",
          });
          console.log(error);
        });
    }
  };

  const downloadSampleCSV = () => {
    // Construct the URL to your sample CSV file located in the public folder
    // Trigger the browser to download the file
    window.location.href = process.env.NEXT_PUBLIC_SAMPLE_TOWER_INFO_CSV;
  };



  const renderFieldGroup = (group, groupName) => {
    return (
      <Box mb={3} sx={{ marginTop: '50px' }}>
        <Typography variant="h6">{groupName}</Typography>
        {group.map((field) => (
          <TextField
            key={field.key}
            fullWidth
            name={field.key}
            label={field.label}
            value={formData[field.key]}
            onChange={handleInputChange}
            margin="normal"
            InputProps={{
              endAdornment: field.unit ? <span>{field.unit}</span> : null,
            }}
          />
        ))}
      </Box>
    );
  };

  return (
    <div>
      <div>
        {(isLoadingForUntimedEffect) && <SmallLoadingEffect isLoading={isLoadingForUntimedEffect} message={"Generating your tower coverage area..."} />}
      </div>
      <Navbar />
      <Container component="main" maxWidth="xl">
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            {/* This will take 3 columns on medium devices and above, and full width on small devices */}
            <Paper elevation={10} sx={{ padding: 3, ...formContainerStyle }}>
              <Typography component="h1" variant="h5" textAlign="center">
                Tower Information
              </Typography>
              <Box mb={3} sx={{ marginTop: '20px', display: 'flex', justifyContent: 'space-between' }}>
                <Box sx={{ width: '48%' }}> {/* Adjust the width as needed */}
                  <Button
                    variant="contained"
                    component="label"
                    fullWidth
                  >
                    Upload CSV
                    <input
                      type="file"
                      hidden
                      onChange={handleFileUpload}
                      accept=".csv"
                    />
                  </Button>
                </Box>
                <Box sx={{ width: '48%' }}> {/* Adjust the width as needed */}
                  <Button
                    variant="contained"
                    onClick={downloadSampleCSV}
                    fullWidth
                  >
                    Download Sample CSV
                  </Button>
                </Box>
              </Box>
              <form onSubmit={handleComputeCoverage}>
                {renderFieldGroup(fieldGroups.towerLocation, 'Tower Location')}
                {renderFieldGroup(fieldGroups.signalStrength, 'Signal Strength')}
                {renderFieldGroup(fieldGroups.antennaInformation, 'Antenna Information')}
                {renderFieldGroup(fieldGroups.filterOptions, 'Filter Options')}
                <Button type="submit" variant="contained" fullWidth>
                  Compute Coverage
                </Button>
                {inPreviewMode && (
                  <Button sx={{ marginTop: '20px', backgroundColor: '#4dc732' }} onClick={saveCoverageClick} variant="contained" fullWidth>
                    Save Coverage
                  </Button>
                )}
              </form>
            </Paper>
          </Grid>
          <Grid item xs={12} md={8}>
            {/* This will take 9 columns on medium devices and above, and full width on small devices */}
            <WirelessCoveragemap imageUrl={imageUrl} transparentImageUrl={transparentImageUrl} bounds={bounds} formData={formData} colorMapping={colorMapping}/>
          </Grid>
        </Grid>

        <Drawer
          anchor="bottom"
          open={saveCoverage}
          onClose={() => setSaveCoverage(false)}
        >
          <div style={{ padding: 20 }}>
            <Typography variant="h6" style={networkInfoHeaderStyle}>
              Please fill in your network information
            </Typography>
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
              <StyledGridItem item xs={12} sm={2}>
                <StyledButton onClick={handleSaveCoverage} variant="contained">
                  Submit
                </StyledButton>
              </StyledGridItem>
            </Grid>
          </div>

        </Drawer>


      </Container>

      <Dialog
        open={openDialog}
        onClose={() => handleDialogClose('stay')}
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <DialogTitle id="alert-dialog-title">{"Your fabric location coverage has been successfully computed saved."}</DialogTitle>
        <DialogActions>
          <Button onClick={() => handleDialogClose('stay')} color="primary">
            Keep Adding Tower
          </Button>
          <Button onClick={() => handleDialogClose('mainPage')} color="secondary" autoFocus>
            View Fabric Location Coverage on Main Page
          </Button>
        </DialogActions>
      </Dialog>




    </div>
  );
};

export default WirelessExtension;
