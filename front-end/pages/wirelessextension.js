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
};

const formContainerStyle = {
  maxHeight: 'calc(100vh)', // replace <Navbar_Height> with the actual height of your Navbar
  overflowY: 'auto',
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
    // ... include other default values as necessary
  });

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

  const handleSubmit = (event) => {
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

  const renderFieldGroup = (group, groupName) => (
    <Box mb={3}>
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

  return (
    <div>
      <div>
        {(isLoadingForUntimedEffect) && <SmallLoadingEffect isLoading={isLoadingForUntimedEffect} />}
      </div>
      <Navbar />
      <Container component="main" maxWidth="xl">
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            {/* Apply the style to this Paper component to make it scrollable */}
            <Paper elevation={10} sx={{ padding: 3, ...formContainerStyle }}>
              <Typography component="h1" variant="h5" textAlign="center">
                Tower Information
              </Typography>
              <form onSubmit={handleSubmit}>
                {renderFieldGroup(fieldGroups.towerLocation, 'Tower Location')}
                {renderFieldGroup(fieldGroups.signalStrength, 'Signal Strength')}
                {renderFieldGroup(fieldGroups.antennaInformation, 'Antenna Information')}
                <Button type="submit" variant="contained" fullWidth>
                  Compute Coverage
                </Button>
              </form>
            </Paper>
          </Grid>
          <Grid item xs={12} md={6}>
            <WirelessCoveragemap imageUrl={imageUrl} bounds={bounds} />
          </Grid>
        </Grid>
      </Container>
    </div>
  );
};

export default WirelessExtension;
