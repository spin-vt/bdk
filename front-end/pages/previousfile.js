import React, { useEffect, useRef, useState, useContext } from "react";
import { useRouter } from 'next/router';
import { TextField, Typography, Container, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, IconButton } from '@material-ui/core';
import { makeStyles } from '@material-ui/core/styles';
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
    width: '100%',
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
  const [files, setFiles] = useState([]);
  const router = useRouter();

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

  return (
    <div>
      <Navbar />
      <Container component="main" maxWidth="md">
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
              overflow: 'hidden' // add scrollbar if content is taller than maxHeight
            }}
          >
            <IconButton onClick={handleClose}><Typography>Close Map</Typography><CloseIcon /></IconButton>
            <Minimap id={viewonlymapid} />
          </Box>
        </Modal>
        <TableContainer component={Paper}>
          <Table className={classes.table} aria-label="simple table">
            <TableHead>
              <TableRow>
                <TableCell>Filename</TableCell>
                <TableCell align="right">Created Time</TableCell>
                <TableCell align="right">Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {files.map((file, index) => (
                <TableRow key={index}>
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
                      </Typography>
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