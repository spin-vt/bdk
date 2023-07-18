import React, { useEffect, useState, useContext } from "react";
import { useRouter } from 'next/router';
import { TextField, Typography, Container, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, IconButton, Grid } from '@material-ui/core';
import { Select, MenuItem, FormControl, InputLabel, Checkbox } from '@material-ui/core';
import { makeStyles, useTheme } from '@material-ui/core/styles';
import Swal from 'sweetalert2';
import DeleteIcon from '@mui/icons-material/Delete';
import { Box } from '@mui/system';
import { Switch, FormControlLabel } from "@material-ui/core";
import { styled } from "@mui/material/styles";
import LayerVisibilityContext from "../contexts/LayerVisibilityContext";
import LoadingEffect from "./LoadingEffect";

const useStyles = makeStyles((theme) => ({
  headertext: {
    marginBottom: '20px',
  },
  table: {
    minWidth: 650,
  },
  container: {
    position: 'relative',
    minWidth: '80%',
    height: '90vh',
    marginTop: '20px'
  },
  deleteButton: {
    color: '#f44336', // Red color
    '&:hover': {
      color: '#d32f2f', // Darker red on hover
    },
  },
}));

const IOSSwitch = styled((props) => (
  <Switch focusVisibleClassName=".Mui-focusVisible" disableRipple {...props} />
))(({ theme }) => ({
  width: 42,
  height: 26,
  padding: 0,
  "& .MuiSwitch-switchBase": {
    padding: 0,
    margin: 2,
    transitionDuration: "300ms",
    "&.Mui-checked": {
      transform: "translateX(16px)",
      color: "#fff",
      "& + .MuiSwitch-track": {
        backgroundColor: theme.palette.mode === "dark" ? "#2ECA45" : "#65C466",
        opacity: 1,
        border: 0,
      },
      "&.Mui-disabled + .MuiSwitch-track": {
        opacity: 0.5,
      },
    },
    "&.Mui-focusVisible .MuiSwitch-thumb": {
      color: "#33cf4d",
      border: "6px solid #fff",
    },
    "&.Mui-disabled .MuiSwitch-thumb": {
      color:
        theme.palette.mode === "light"
          ? theme.palette.grey[100]
          : theme.palette.grey[600],
    },
    "&.Mui-disabled + .MuiSwitch-track": {
      opacity: theme.palette.mode === "light" ? 0.7 : 0.3,
    },
  },
  "& .MuiSwitch-thumb": {
    boxSizing: "border-box",
    width: 22,
    height: 22,
  },
  "& .MuiSwitch-track": {
    borderRadius: 26 / 2,
    backgroundColor: theme.palette.mode === "light" ? "#E9E9EA" : "#39393D",
    opacity: 1,
    transition: theme.transitions.create(["background-color"], {
      duration: 500,
    }),
  },
}));


const MyFile = () => {

  const classes = useStyles();
  const theme = useTheme();
  const [fabricFiles, setFabricFiles] = useState([]);
  const [networkDataFiles, setNetworkDataFiles] = useState([]);
  const [manualEditFiles, setManualEditFiles] = useState([]);

  const { setLayers } = useContext(LayerVisibilityContext);

  const [isLoading, setIsLoading] = useState(false);
  const [isDataReady, setIsDataReady] = useState(false);
  const loadingTimeInMs = 2 * 60 * 1000;

  const router = useRouter();



  const fetchFiles = async () => {
    const response = await fetch("http://localhost:5000/api/files", {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // Include cookies in the request
    });

    if (response.status === 401) {
      Swal.fire({
        icon: 'error',
        title: 'Oops...',
        text: 'Session expired, please log in again!'
      });
      // Redirect to login page
      router.push('/login');
      return;
    }

    const data = await response.json();
    data.forEach(file => {
      console.log(file);
      const formattedFile = {
        id: file.id,
        name: file.name,
        uploadDate: new Date(file.timestamp).toLocaleString(),
        type: file.type,
      };
      if (file.name.endsWith('.csv')) {
        setFabricFiles(prevFiles => [...prevFiles, formattedFile]);
      } else if (file.name.endsWith('.kml')) {
        setNetworkDataFiles(prevFiles => [...prevFiles, formattedFile]);
        setLayers(prevLayers => ({
          ...prevLayers,
          [file.name]: true, // Set the visibility of the layer to true
        }));
      } else if (file.name.endsWith('/')) {
        setManualEditFiles(prevFiles => [...prevFiles, formattedFile]);
      }
    });
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  const handleDelete = async (id, setFiles) => {
    setIsLoading(true);
    try {
      const response = await fetch(`http://localhost:5000/api/delfiles/${id}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include', // Include cookies in the request
      });
  
      if (response.status === 401) {
        setIsLoading(false);
        Swal.fire({
          icon: 'error',
          title: 'Oops...',
          text: 'Session expired, please log in again!'
        });
        // Redirect to login page
        router.push('/login');
        return;
      }
  
      if (response.ok) {
        setFiles(prevFiles => prevFiles.filter((file) => file.id !== id));
        setIsDataReady(true);
        setIsLoading(false);
        setTimeout(() => {
          setIsDataReady(false);
        }, 5000);
      } else {
        throw new Error('Response was not OK');
      }
    } catch (error) {
      setIsLoading(false);
      console.error('An error occurred:', error);
    }
  };


  return (
    <div>
      {(isLoading || isDataReady) && (
        <LoadingEffect
          isLoading={isLoading}
          loadingTimeInMs={loadingTimeInMs}
        />
      )}
      <Container component="main" maxWidth="md" className={classes.container}>
        <Typography component="h1" variant="h5" className={classes.headertext}>
          Your Uploaded Files
        </Typography>
        {/* Fabric Files Table */}
        <Typography component="h2" variant="h6" className={classes.headertext}>
          Fabric Files
        </Typography>
        <FileTable files={fabricFiles} handleDelete={handleDelete} setFiles={setFabricFiles} classes={classes} showSwitch={false} />

        {/* Network Data Files Table */}
        <Typography component="h2" variant="h6" className={classes.headertext}>
          Network Data Files
        </Typography>
        <FileTable files={networkDataFiles} handleDelete={handleDelete} setFiles={setNetworkDataFiles} classes={classes} showSwitch={true} />

        {/* Manual Edit Files Table */}
        <Typography component="h2" variant="h6" className={classes.headertext}>
          Manual Edits
        </Typography>
        <FileTable files={manualEditFiles} handleDelete={handleDelete} setFiles={setManualEditFiles} classes={classes} showSwitch={false} />
      </Container>
    </div>
  );
};

// New FileTable Component to avoid code duplication
const FileTable = ({ files, handleDelete, setFiles, classes, showSwitch }) => {
  const { setLayers } = useContext(LayerVisibilityContext);
  const [checked, setChecked] = useState([]);

  useEffect(() => {
    setChecked(new Array(files.length).fill(true));
  }, [files]);

  const handleToggle = (i) => () => {
    const newChecked = [...checked];
    newChecked[i] = !newChecked[i];
    setChecked(newChecked);

    // Update the layers visibility state
    setLayers(prevLayers => ({
      ...prevLayers,
      [files[i].name]: newChecked[i],
    }));
  };

  if (checked.length !== files.length) {
    return null; // or return a loading spinner
  };

  return (
    <TableContainer component={Paper}>
      <Table className={classes.table} aria-label="file table">
        <TableHead>
          <TableRow>
            <TableCell>Filename</TableCell>
            <TableCell >Created Time</TableCell>
            <TableCell align="right">Type</TableCell>
            {showSwitch && <TableCell align="right">Show on Map</TableCell>}
            <TableCell align="right">Action</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {files.map((file, index) => (
            <TableRow key={index}>
              <TableCell component="th" scope="row">
                {file.name}
              </TableCell>
              <TableCell>{file.uploadDate}</TableCell>
              <TableCell align="right">
                {file.type}
              </TableCell>
              {showSwitch && <TableCell align="right">
                <IOSSwitch
                  sx={{ m: 1 }}
                  checked={checked[index]}
                  onChange={handleToggle(index)}
                  name="showOnMapSwitch"
                  inputProps={{ 'aria-label': 'secondary checkbox' }}
                />
              </TableCell>}
              <TableCell align="right">
                <IconButton className={classes.deleteButton} onClick={() => handleDelete(file.id, setFiles)}>
                  <DeleteIcon />
                  <Typography sx={{ marginLeft: '10px' }}>
                    Delete File
                  </Typography>
                </IconButton>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};
export default MyFile;
