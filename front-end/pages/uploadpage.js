import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { makeStyles } from "@material-ui/core/styles";
import Button from "@material-ui/core/Button";
import List from "@material-ui/core/List";
import ListItem from "@material-ui/core/ListItem";
import Typography from "@material-ui/core/Typography";
import Grid from "@material-ui/core/Grid";
import Container from "@material-ui/core/Container";
import Navbar from "../components/Navbar";
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';

const useStyles = makeStyles((theme) => ({
  outmostContainer: {
    minHeight: "95vh",
    minWidth: "100vh",
    display: "flex",
    flexDirection: "column",
    // alignItems: "center",
    // justifyContent: "center",
    backgroundColor: `#f8f8ff`
  },
  innerContainer: {
    minHeight: "70vh",
    minWidth: "90vw",
    paddingTop: theme.spacing(8),
    paddingLeft: theme.spacing(16),
    borderStyle: "solid",
    borderWidth: "5px",
    borderColor: `#f8f8ff`,
    backgroundColor: "white",
    marginTop: "8vh",
    marginLeft: "3vw",
    marginRight: "3vw",
  },
//   grid: {
//     marginTop
//   },
  uploadDropzone: {
    border: "3px dashed lightgray",
    padding: theme.spacing(2),
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "50vh",
    marginTop: theme.spacing(4),
    // marginRight: theme.spacing(16),
    backgroundColor: `#f8f8ff`,
  },
  dropZoneDiv: {
    marginTop: theme.spacing(4),
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
  },
  dropZoneItem: {
    marginTop: theme.spacing(1),
  },
  uploadFilesContainer: {
    marginTop: theme.spacing(2),
  },
}));

export default function UploadPage() {
  const classes = useStyles();
  const [files, setFiles] = useState([]);

  const onDrop = useCallback((acceptedFiles) => {
    setFiles((prevFiles) => [...prevFiles, ...acceptedFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  return (
    <div>
      <Navbar />
      <div className={classes.outmostContainer}>
        <div className={classes.innerContainer}>
          
            <Grid container justifyContent="flex-start">
              <Grid item xs={4}>
                <Typography variant="body1" style={{ fontSize: "30px", marginTop: "30px"}}>
                  Upload File
                </Typography>
                <div {...getRootProps()} className={classes.uploadDropzone}>
                  <input {...getInputProps()} />
                  
                  <Typography className={classes.dropZoneItem} style={{ fontWeight: 'bold' }}>Drag and Drop files here</Typography>
                  <Typography className={classes.dropZoneItem}>OR</Typography>
                  <Button variant="contained" color="secondary" className={classes.dropZoneItem}>
                    <AddCircleOutlineIcon style={{marginRight:'4px'}}/>
                    Add files
                  </Button>
                  <div className={classes.dropZoneDiv}>
                  <Typography className={classes.dropZoneItem} style={{ fontWeight: 'bold' }}>Supports file formats:</Typography>
                  <Typography className={classes.dropZoneItem}>csv, xlsx</Typography>
                  </div>
                </div>
              </Grid>
              <Grid item xs={8}>
                <Typography>Files to be uploaded:</Typography>
                <div className={classes.uploadFilesContainer}>
                  <List>
                    {files.map((file, index) => (
                      <ListItem key={index}>{file.name}</ListItem>
                    ))}
                  </List>
                </div>
              </Grid>
            </Grid>
           
          
        </div>
      </div>
    </div>
  );
}
