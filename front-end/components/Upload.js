import * as React from 'react';
import Button from '@mui/material/Button';
import ButtonGroup from '@mui/material/ButtonGroup';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import ClickAwayListener from '@mui/material/ClickAwayListener';
import Grow from '@mui/material/Grow';
import Paper from '@mui/material/Paper';
import Popper from '@mui/material/Popper';
import MenuItem from '@mui/material/MenuItem';
import MenuList from '@mui/material/MenuList';
import Box from '@mui/material/Box';
import ExportButton from './Export';
import { DataGrid } from '@mui/x-data-grid';
import Select from '@mui/material/Select';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import { makeStyles } from '@mui/styles';
import Grid from '@mui/material/Grid';

const useStyles = makeStyles({
  formControl: {
    margin: '4px',
    minWidth: '150px',  
    backgroundColor: 'white', 
    borderRadius: '4px', 
    height: '25px',
    display: 'flex',
    alignItems: 'center'
  },
  inputLabel: {
    fontSize: '0.875rem',
    top: '-000px'
  },
  select: {
    height: '25px',
    padding: '0 0 0 10px',
    minWidth:'150px',
  },
});

const options = ['Fabric', 'Network'];
let storage = [];

const tech_types = {
  'Copper Wire': 10,
  'Coaxial Cable / HFC': 40,
  'Optical Carrier / Fiber to the Premises': 50,
  'Geostationary Satellite': 60,
  'Non-geostationary Satellite': 61,
  'Unlicensed Terrestrial Fixed Wireless': 70,
  'Licensed Terrestrial Fixed Wireless': 71,
  'Licensed-by-Rule Terrestrial Fixed Wireless': 72,
  'Other': 0,
};

//Map key component

function MapKey() {
  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      <span style={{ height: '10px', width: '10px', backgroundColor: 'Green', display: 'inline-block', marginRight: '5px' }}></span>
      <span style={{ marginRight: '15px' }}>Served</span>
      <span style={{ height: '10px', width: '10px', backgroundColor: 'Red', display: 'inline-block', marginRight: '5px' }}></span>
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
  const [selectedFiles, setSelectedFiles] = React.useState(
    JSON.parse(localStorage.getItem('selectedFiles')) || []
  );
  const [downloadSpeed, setDownloadSpeed] = React.useState('');
  const [uploadSpeed, setUploadSpeed] = React.useState('');
  const [techType, setTechType] = React.useState('');
  const idCounterRef = React.useRef(1); // Counter for generating unique IDs
  const [exportSuccess, setExportSuccess] = React.useState(
    localStorage.getItem('exportSuccess') === 'true' || false
  );
  const [buttonGroupWidth, setButtonGroupWidth] = React.useState(null);

  const handleDownloadClick = (event) => {
    event.preventDefault();
    
    const params = new URLSearchParams({
      downloadSpeed: downloadSpeed,
      uploadSpeed: uploadSpeed,
      techType: techType,
    });
    
    window.location.href = `http://localhost:8000/export?${params.toString()}`;
  };


  const handleExportClick = (event) => {
    event.preventDefault();
  
    const formData = new FormData();
  
    storage.forEach((file) => {
      const fileData = {
        file: file[0],
        downloadSpeed: options[selectedIndex] === 'Network' ? downloadSpeed : '',
        uploadSpeed: options[selectedIndex] === 'Network' ? uploadSpeed : '',
        techType: options[selectedIndex] === 'Network' ? techType : '',
      };
  
      formData.append('fileData', JSON.stringify(fileData));
      formData.append('file', file[0]);
    });
  
    fetch('http://localhost:8000/submit-fiber-form', {
      method: 'POST',
      body: formData,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        fetchMarkers(downloadSpeed, uploadSpeed, techType);
        console.log("will show new buttons soon 1")
        console.log('Status:', response); // log the status
        setExportSuccess(true); // Set the export success state to true
        return response.json();
      })
      .then((data) => {
        console.log('Success:', data);
        console.log("going to fetch markers")
        console.log("Will show new buttons soon 2")
        setExportSuccess(true); // Set the export success state to true
        fetchMarkers(downloadSpeed, uploadSpeed, techType);
      })
      .catch((error) => {
        fetchMarkers(downloadSpeed, uploadSpeed, techType);
        console.error('Error:', error);
      });
  };
  
  // Call fetchMarkers when the Export button is clicked
  React.useEffect(() => {
    if (exportSuccess) {
      const dynamicMap = document.getElementById('dynamic-map');
      if (dynamicMap) {
        dynamicMap.fetchMarkers(); // Call fetchMarkers function in the DynamicMap component
      }
    }
    if (buttonGroupRef.current) {
      setButtonGroupWidth(buttonGroupRef.current.offsetWidth);
    }
  }, [exportSuccess, buttonGroupRef]);

  const handleFileChange = (event) => {
    storage.push([event.target.files[0], idCounterRef.current]);

      const newFiles = Object.values(event.target.files).map((file) => ({
      id: idCounterRef.current++,
      name: file.name,
      option: options[selectedIndex], // Track the selected option for each file
      downloadSpeed: options[selectedIndex] === 'Network' ? downloadSpeed : '',
      uploadSpeed: options[selectedIndex] === 'Network' ? uploadSpeed : '',
      techType: options[selectedIndex] === 'Network' ? techType : '',
    }));
    
    idCounterRef.current += 1;

    const updatedFiles = [...selectedFiles, ...newFiles];
    setSelectedFiles(updatedFiles);
    localStorage.setItem('selectedFiles', JSON.stringify(updatedFiles));
  };

  const handleClick = () => {
    console.info(`You clicked ${options[selectedIndex]}`);
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
    for (let i = 0; i < storage.length; i++) {
        if (storage[i][1] === id) {
            storage.splice(i, 1);
            break;
        }
    }

    // Update selectedFiles state
    setSelectedFiles((prevFiles) => prevFiles.filter((file) => file.id !== id));
    setExportSuccess(false); // Set the export success state to true

    // Update local storage
    const updatedFiles = JSON.parse(localStorage.getItem('selectedFiles')) || [];
    const filteredFiles = updatedFiles.filter((file) => file.id !== id);
    localStorage.setItem('selectedFiles', JSON.stringify(filteredFiles));

    // Reset the file input element
    const fileInput = anchorRef.current;
    if (fileInput) {
        fileInput.value = '';
    }
};

  const columns = [
    { field: 'id', headerName: 'ID', width: 90 },
    {
      field: 'name',
      headerName: 'File Name',
      width: 100,
      editable: true,
    },
    {
      field: 'option',
      headerName: 'Option',
      width: 100,
    },
    {
      field: 'downloadSpeed',
      headerName: 'Download Speed',
      width: 150,
      hide: selectedIndex !== 1, // Hide the column when "Network" is not selected
    },
    {
      field: 'uploadSpeed',
      headerName: 'Upload Speed',
      width: 150,
      hide: selectedIndex !== 1, // Hide the column when "Network" is not selected
    },
    {
      field: 'techType',
      headerName: 'Tech Type',
      width: 100,
      hide: selectedIndex !== 1, // Hide the column when "Network" is not selected
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      renderCell: (params) => (
        <Button onClick={() => handleDelete(params.row.id)} color="error" variant="outlined" size="small">
          Delete
        </Button>
      ),
    },
  ];

  React.useEffect(() => {
    // Store the exportSuccess state in local storage whenever it changes
    localStorage.setItem('exportSuccess', exportSuccess);
  }, [exportSuccess]);

  return (
    <React.Fragment>
      <ButtonGroup variant="contained" ref={buttonGroupRef} aria-label="split button">
        <Button onClick={handleClick}>{options[selectedIndex]}</Button>
        <Button
          size="small"
          aria-controls={open ? 'split-button-menu' : undefined}
          aria-expanded={open ? 'true' : undefined}
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
                placement === 'bottom' ? 'center top' : 'center bottom',
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
        <Box sx={{ marginTop: '1rem' }}>
        <Grid container spacing={3}>
          <Grid item xs={12} sm={4}>
            <label htmlFor="downloadSpeed">Download Speed (Mgps): </label>
            <input
              type="text"
              id="downloadSpeed"
              value={downloadSpeed}
              onChange={(e) => setDownloadSpeed(e.target.value)}
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <label htmlFor="uploadSpeed">Upload Speed (Mgps): </label>
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
                    {key}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Box>      
      )}
      {/* Hidden file input to allow file selection */}
      <input
        type="file"
        style={{ display: 'none' }}
        onChange={handleFileChange}
        ref={anchorRef}
      />
      {/* Display the uploaded files in a DataGrid */}
      <Box sx={{ height: 400 }} style={{ marginTop: '3vh' }}>
        <DataGrid
          rows={selectedFiles}
          columns={columns}
          pageSize={5}
          checkboxSelection
        />
      </Box>
      <Box sx={{ display: 'flex', marginTop: '1rem', gap: '1rem' }}>
        <ExportButton onClick={handleExportClick} />
        {exportSuccess && (
          <Button variant="contained" onClick={handleDownloadClick}>
            Download CSV
          </Button>
        )}
        <MapKey/>
      </Box>
    </React.Fragment>
  );
}
