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

const options = ['Fabric', 'Tower Data', 'LTE Data'];
let storage = [];

export default function Upload({ fetchMarkersWireless }) {
  const [open, setOpen] = React.useState(false);
  const anchorRef = React.useRef(null);
  const buttonGroupRef = React.useRef(null);
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const [selectedFiles, setSelectedFiles] = React.useState([]);
  const [downloadSpeed, setDownloadSpeed] = React.useState('');
  const [uploadSpeed, setUploadSpeed] = React.useState('');
  const [techType, setTechType] = React.useState('');
  const [ispName, setISPName] = React.useState('');
  const idCounterRef = React.useRef(1); // Counter for generating unique IDs
  const [exportSuccess, setExportSuccess] = React.useState(false);
  const [buttonGroupWidth, setButtonGroupWidth] = React.useState(null);

  const handleDownloadClick = (event) => {
    event.preventDefault();
    window.location.href = 'http://localhost:8000/export-wireless';
  };
  
  const handleExportClick = (event) => {
    event.preventDefault();
  
    const formData = new FormData();
  
    storage.forEach((file) => {
      const fileData = {
        file: file[0],
        ispName: options[selectedIndex] === 'Network' ? ispName : '',
        downloadSpeed: options[selectedIndex] === 'Network' ? downloadSpeed : '',
        uploadSpeed: options[selectedIndex] === 'Network' ? uploadSpeed : '',
        techType: options[selectedIndex] === 'Network' ? techType : '',
      };
  
      formData.append('fileData', JSON.stringify(fileData));
      formData.append('file', file[0]);
    });
  
    fetch('http://localhost:8000/submit-wireless-form', {
      method: 'POST',
      body: formData,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        // fetchMarkers();
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
        // fetchMarkers();
      })
      .catch((error) => {
        // fetchMarkers();
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

    const newFiles = Array.from(event.target.files);
    const updatedFiles = newFiles.map((file) => ({
      id: idCounterRef.current++,
      name: file.name,
      option: options[selectedIndex], // Track the selected option for each file
      ispName: options[selectedIndex] === 'Network' ? ispName : '',
      downloadSpeed: options[selectedIndex] === 'Network' ? downloadSpeed : '',
      uploadSpeed: options[selectedIndex] === 'Network' ? uploadSpeed : '',
      techType: options[selectedIndex] === 'Network' ? techType : '',
    }));
    setSelectedFiles((prevFiles) => [...prevFiles, ...updatedFiles]);
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
    let i = 0;
    storage.forEach((file) => {
      if (file[1] === id) { 
        storage.splice(i, 1);
      }
      i++;
    });
    
    setSelectedFiles((prevFiles) => prevFiles.filter((file) => file.id !== id));

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
      field: 'ispName',
      headerName: 'ISP Name',
      width: 100,
      hide: selectedIndex !== 1, // Hide the column when "Network" is not selected
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
          <div>
            <div>
              <label htmlFor="ispName">ISP Name: </label>
              <input
                type="text"
                id="ispName"
                value={ispName}
                onChange={(e) => setISPName(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="downloadSpeed">Download Speed: </label>
              <input
                type="text"
                id="downloadSpeed"
                value={downloadSpeed}
                onChange={(e) => setDownloadSpeed(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="uploadSpeed">Upload Speed: </label>
              <input
                type="text"
                id="uploadSpeed"
                value={uploadSpeed}
                onChange={(e) => setUploadSpeed(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="techType">Tech Type: </label>
              <input
                type="text"
                id="techType"
                value={techType}
                onChange={(e) => setTechType(e.target.value)}
              />
            </div>
          </div>
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
      </Box>
    </React.Fragment>
  );
}
