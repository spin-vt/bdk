import React, { useEffect, useRef, useState, useContext } from "react";
import { useRouter } from 'next/router';
import { TextField, Button, Typography, Container, List, ListItem, ListItemText, ListItemSecondaryAction, IconButton } from '@material-ui/core';
import { makeStyles } from '@material-ui/core/styles';
import Link from 'next/link'
import Navbar from '../components/Navbar';
import Swal from 'sweetalert2';
import DeleteIcon from '@mui/icons-material/Delete';
import ClearIcon from '@mui/icons-material/Clear';

const useStyles = makeStyles((theme) => ({
  container: {
    position: 'relative',
    width: '100%',
    height: '90vh',
    marginTop: '20px'
  },
  deleteButton: {
    backgroundColor: '#f44336', // Red color
    color: '#fff', // White color
    '&:hover': {
      backgroundColor: '#d32f2f', // Darker red on hover
    },
    borderRadius: '10px',
    padding: '4px',
    margin: '4px',
    border: 'none',
    cursor: 'pointer',
  },
}));




const PreviousFile = () => {

  const classes = useStyles();
  const [files, setFiles] = useState([]);
  
  const fetchMbtiles = async () => {
    fetch("http://localhost:5000/api/mbtiles") // replace with your Flask server URL if it's not on the same domain
    .then(response => response.json())
    .then(data => {
      setFiles(data.map(file => ({
        name: file.filename,
        uploadDate: new Date(file.timestamp).toLocaleDateString()
      })));
    })
    .catch((error) => {
      console.error('Error:', error);
    });
  };

  useEffect(() => {
    fetchMbtiles();
  }, []);

  const handleDelete = (index) => {
    setFiles(prevFiles => prevFiles.filter((file, i) => i !== index));
  };

  return (
    <div>
      <Navbar />
      <Container component="main" maxWidth="xs" className={classes.container} >
        <div>
          <Typography component="h1" variant="h5">
            Your previous uploads
          </Typography>
          <List >
            {files.map((file, index) => (
              <ListItem key={index}>
                <ListItemText primary={file.name} secondary={file.uploadDate} />
                <ListItemSecondaryAction>
                  <button className={classes.deleteButton} onClick={() => handleDelete(index)}>
                    <DeleteIcon />
                  </button>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        </div>
      </Container>
    </div>
  );
};

export default PreviousFile;