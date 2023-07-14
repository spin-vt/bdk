import React, { useEffect, useRef, useState, useContext } from "react";
import { useRouter } from 'next/router';
import { TextField, Typography, Container, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, IconButton, Typography } from '@material-ui/core';
import { Select, MenuItem, FormControl, InputLabel, Checkbox, Grid } from '@material-ui/core';
import { makeStyles, useTheme } from '@material-ui/core/styles';
import Link from 'next/link'
import Navbar from '../components/Navbar';
import Swal from 'sweetalert2';
import DeleteIcon from '@mui/icons-material/Delete';
import ClearIcon from '@mui/icons-material/Clear';
import MapIcon from '@mui/icons-material/Map';
import MbtilesContext from '../components/MbtilesContext';
import Modal from '@mui/material/Modal';
import { Box } from '@mui/system';
import CloseIcon from '@mui/icons-material/Close';
import EditIcon from '@mui/icons-material/Edit';
import MergeIcon from '@mui/icons-material/Merge';
import Searchbar from "../components/Searchbar";

import dynamic from 'next/dynamic';

const Minimap = dynamic(
  () => import('../components/Minimap'),
  { ssr: false }
);



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




const PreviousFile = () => {

  const classes = useStyles();
  const theme = useTheme();
  const [files, setFiles] = useState([]);
  const router = useRouter();

  const [selectedFiles, setSelectedFiles] = useState([]);
  const [sortBy, setSortBy] = useState('newest');

  // Inside your component
  const { setMbtid } = useContext(MbtilesContext);

  const [viewonlymapid, setViewonlymapid] = useState(null);

  const [open, setOpen] = useState(false);

  const handleOpen = () => setOpen(true);
  const handleClose = () => setOpen(false);

  const fetchMbtiles = async () => {
    const response = await fetch("http://localhost:5000/api/mbtiles", {
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
    setFiles(data.map(file => ({
      id: file.id,
      name: file.filename,
      uploadDate: new Date(file.timestamp).toLocaleString()
    })));
  };

  useEffect(() => {
    fetchMbtiles();
  }, []);

  const handleDelete = async (index) => {
    const file = files[index];
    const response = await fetch(`http://localhost:5000/api/delmbtiles/${file.id}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // Include cookies in the request
    });

    if (response.ok) {
      setFiles(prevFiles => prevFiles.filter((file, i) => i !== index));
    } else {
      console.log(error);
    }
  };

  const handleEditMap = (index) => {
    const file = files[index];
    setMbtid(file.id);
    router.push("/");
  };

  const handleViewMap = (index) => {
    const file = files[index];
    setViewonlymapid(file.id);
    handleOpen();
  };

  useEffect(() => {
    setFiles(prevFiles => [...prevFiles].sort((a, b) => {
      if (sortBy === 'newest') {
        return new Date(b.uploadDate) - new Date(a.uploadDate);
      } else if (sortBy === 'oldest') {
        return new Date(a.uploadDate) - new Date(b.uploadDate);
      } else {
        return 0;
      }
    }));
  }, [sortBy]);

  return (
    <div>
      <Navbar />
      <Container component="main" maxWidth="md" className={classes.container}>
        <Typography component="h1" variant="h5" className={classes.headertext}>
          Your Uploaded Files
        </Typography>
        <Modal
          open={open}
          onClose={handleClose}
          aria-labelledby="map-modal-title"
          aria-describedby="map-modal-description"
        >
          <Box
            sx={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              width: '80%', // 80% width of the viewport
              maxHeight: '80%', // 80% max height of the viewport
              bgcolor: 'background.paper',
              boxShadow: 24,
              p: 4,
              overflow: 'hidden', // add scrollbar if content is taller than maxHeight
            }}
          >
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                width: '100%',
                marginBottom: '20px',
              }}
            >
              <IconButton onClick={handleClose}><Typography>Close Map</Typography><CloseIcon /></IconButton>
              <Searchbar />
            </Box>
            <Minimap id={viewonlymapid} />
          </Box>
        </Modal>
        <TableContainer component={Paper}>
          <Box display="flex" justifyContent="flex-end" p={1} border={1} borderColor={theme.palette.divider}>
            <Grid container alignItems="center" justifyContent="flex-end">
              <Grid item style={{ marginRight: '30px' }}>
                <IconButton
                  onClick={() => handleMergeSelected()} // Here create and use handleMergeSelected
                >
                  {/* Assuming you have a MergeIcon */}
                  <MergeIcon />
                  <Typography sx={{ marginLeft: '10px' }}>
                    Merge Selected Files
                  </Typography>
                </IconButton>
                <IconButton
                  className={classes.deleteButton}
                  onClick={() => handleDeleteSelected()} // Here create and use handleDeleteSelected
                >
                  <DeleteIcon />
                  <Typography sx={{ marginLeft: '10px' }}>
                    Delete Selected Files
                  </Typography>
                </IconButton>
              </Grid>
              <Grid item>
                <FormControl>
                  <InputLabel id="sort-by-label">Sort by</InputLabel>
                  <Select
                    labelId="sort-by-label"
                    id="sort-by-select"
                    value={sortBy}
                    onChange={e => setSortBy(e.target.value)}
                  >
                    <MenuItem value={'newest'}>Newest First</MenuItem>
                    <MenuItem value={'oldest'}>Oldest First</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          </Box>
          <Table className={classes.table} aria-label="file table">
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Checkbox
                    indeterminate={selectedFiles.length > 0 && selectedFiles.length < files.length}
                    checked={files.length > 0 && selectedFiles.length === files.length}
                    onChange={(event) => {
                      if (event.target.checked) {
                        setSelectedFiles(files.map((file, index) => index));
                      } else {
                        setSelectedFiles([]);
                      }
                    }}
                  />
                </TableCell>
                <TableCell>Filename</TableCell>
                <TableCell align="right">Created Time</TableCell>
                <TableCell align="right">Action</TableCell>

              </TableRow>
            </TableHead>
            <TableBody>
              {files.map((file, index) => (
                <TableRow key={index}>
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={selectedFiles.indexOf(index) !== -1}
                      onChange={(event) => {
                        if (event.target.checked) {
                          setSelectedFiles([...selectedFiles, index]);
                        } else {
                          setSelectedFiles(selectedFiles.filter(i => i !== index));
                        }
                      }}
                    />
                  </TableCell>
                  <TableCell component="th" scope="row">
                    {file.name}
                  </TableCell>
                  <TableCell align="right">{file.uploadDate}</TableCell>
                  <TableCell align="right">
                    <IconButton className={classes.mapButton} onClick={() => handleEditMap(index)}>
                      <EditIcon />
                      <Typography sx={{ marginLeft: '10px' }}>
                        Edit map
                      </Typography>
                    </IconButton>
                    <IconButton className={classes.deleteButton} onClick={() => handleDelete(index)}>
                      <DeleteIcon />
                      <Typography sx={{ marginLeft: '10px' }}>
                        Delete map
                      </Typography>
                    </IconButton>
                    <IconButton onClick={() => handleViewMap(index)}>
                      <MapIcon />
                      <Typography sx={{ marginLeft: '10px' }}>
                        View this Map
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Container>
    </div>
  );
};

export default PreviousFile;