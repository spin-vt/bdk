import React, { useState } from 'react';
import Navbar from '../components/Navbar';
import SmallLoadingEffect from '../components/SmallLoadingEffect';
import WirelessCoveragemap from '../components/WirelessCoveragemap';
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
} from '@mui/material';
import Swal from 'sweetalert2';


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
    // ... other antenna information fields
  ],
  filterOptions: [
    { key: 'floorLossRate', label: 'Floor Loss Rate', unit: 'dB' },
    // ... other filter option fields if needed
  ],
};

const formContainerStyle = {
  maxHeight: 'calc(100vh)', // replace <Navbar_Height> with the actual height of your Navbar
  overflowY: 'auto',
};

const ColorPalette = ({ mapping }) => {
  // Convert the mapping object into an array of elements
  const paletteElements = Object.entries(mapping).map(([loss, rgb]) => {
    const style = {
      backgroundColor: `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`,
      width: '100%',
      height: '20px', // or any other height
      margin: '2px 0',
      color: 'white',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    };
    return (
      <div key={loss} style={style}>
        {loss} dB
      </div>
    );
  });

  return <div>
    <Typography>Loss Rate(dB)</Typography>
    {paletteElements}</div>;
};

const WirelessExtension = () => {

  const [isLoadingForUntimedEffect, setIsLoadingForUntimedEffect] = useState(false);
  const [formData, setFormData] = useState({
    towername: '',
    latitude: '',
    longitude: '',
    // erp: '',
    frequency: '',
    radius: '',
    antennaHeight: '',
    antennaTilt: '',
    horizontalFacing: '',
    floorLossRate: 150,
    // ... include other default values as necessary
  });
  const [inPreviewMode, setInPreviewMode] = useState(false);
  const [colorMapping, setColorMapping] = useState({});

  const [imageUrl, setImageUrl] = useState(''); // replace with actual state logic
  const [bounds, setBounds] = useState({
    north: 39.5, east: -98.5, south: 39.5, west: -98.5
  });

  const handleInputChange = (event) => {
    const { name, value } = event.target;
    setFormData((prevFormData) => ({
      ...prevFormData,
      [name]: value,
    }));
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

  const handleSaveCoverage = (event) => {
    event.preventDefault();
    setIsLoadingForUntimedEffect(true);
    fetch(`${backend_url}/api/compute-wireless-prediction-fabric-coverage`, {
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
            floorLossRate: data[0].floorLossRate || 150
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
                  <Button sx={{marginTop: '20px', backgroundColor: '#4dc732'}} onClick={handleSaveCoverage} variant="contained" fullWidth>
                    Save Coverage
                  </Button>
                )}
              </form>
            </Paper>
          </Grid>
          <Grid item xs={12} md={8}>
            {/* This will take 9 columns on medium devices and above, and full width on small devices */}
            <WirelessCoveragemap imageUrl={imageUrl} bounds={bounds}/>
            <ColorPalette mapping={colorMapping}/>
          </Grid>
        </Grid>
      </Container>

    </div>
  );
};

export default WirelessExtension;
