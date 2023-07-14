import React, { useEffect, useState, useContext } from "react";
import { useRouter } from 'next/router';
import { TextField, Typography, Container, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, IconButton, Grid } from '@material-ui/core';
import { Select, MenuItem, FormControl, InputLabel, Checkbox } from '@material-ui/core';
import { makeStyles, useTheme } from '@material-ui/core/styles';
import Swal from 'sweetalert2';
import DeleteIcon from '@mui/icons-material/Delete';
import { Box } from '@mui/system';

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

const MyFile = () => {

  const classes = useStyles();
  const theme = useTheme();
  const [fabricFiles, setFabricFiles] = useState([]);
  const [networkDataFiles, setNetworkDataFiles] = useState([]);
  const [manualEditFiles, setManualEditFiles] = useState([]);
  const router = useRouter();
  const [files, setFiles] = useState([]);

  const [selectedFiles, setSelectedFiles] = useState([]);
  const [sortBy, setSortBy] = useState('newest');


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
      const formattedFile = {
        id: file.id,
        name: file.name,
        uploadDate: new Date(file.timestamp).toLocaleString()
      };
      if (file.name.endsWith('.csv')) {
        setFabricFiles(prevFiles => [...prevFiles, formattedFile]);
      } else if (file.name.endsWith('.kml')) {
        setNetworkDataFiles(prevFiles => [...prevFiles, formattedFile]);
      } else if (file.name.endsWith('/')) {
        setManualEditFiles(prevFiles => [...prevFiles, formattedFile]);
      }
    });
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  const handleDelete = async (index) => {
    const file = files[index];
    const response = await fetch(`http://localhost:5000/api/files/${file.id}`, {
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
      <Container component="main" maxWidth="md" className={classes.container}>
        <Typography component="h1" variant="h5" className={classes.headertext}>
          Your Uploaded Files
        </Typography>
        {/* Fabric Files Table */}
        <Typography component="h2" variant="h6" className={classes.headertext}>
          Fabric Files
        </Typography>
        <FileTable files={fabricFiles} handleDelete={handleDelete} classes={classes} />
        
        {/* Network Data Files Table */}
        <Typography component="h2" variant="h6" className={classes.headertext}>
          Network Data Files
        </Typography>
        <FileTable files={networkDataFiles} handleDelete={handleDelete} classes={classes} />
        
        {/* Manual Edit Files Table */}
        <Typography component="h2" variant="h6" className={classes.headertext}>
          Manual Edits
        </Typography>
        <FileTable files={manualEditFiles} handleDelete={handleDelete} classes={classes} />
      </Container>
    </div>
  );
};

// New FileTable Component to avoid code duplication
const FileTable = ({ files, handleDelete, classes }) => {
  return (
    <TableContainer component={Paper}>
      <Table className={classes.table} aria-label="file table">
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
                <IconButton className={classes.deleteButton} onClick={() => handleDelete(index)}>
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