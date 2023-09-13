import React, { useEffect, useState, useContext } from "react";
import { useRouter } from "next/router";
import { Typography, Container, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, IconButton } from "@mui/material";
import { styled } from "@mui/material/styles";
import DeleteIcon from "@mui/icons-material/Delete";
import MapIcon from "@mui/icons-material/Map";
import Swal from "sweetalert2";
import MbtilesContext from "../contexts/MbtilesContext";
import { backend_url } from "../utils/settings";

const HeaderText = styled(Typography)({
  marginBottom: "20px",
  marginTop: "20px",
});

const StyledTable = styled(Table)({
  minWidth: 650,
});

const StyledContainer = styled(Container)({
  zIndex: 1000,
  position: "relative",
  minWidth: "80%",
  height: "90vh",
  marginTop: "20px"
});

const StyledIconButton = styled(IconButton)({
  color: "#f44336",
  "&:hover": {
    color: "#d32f2f",
  },
});



const PreviousExport = () => {

  const [folders, setFolders] = useState([]);
  const router = useRouter();

  // Inside your component
  const { setMbtid } = useContext(MbtilesContext);


  const fetchExportedFiles = async () => {
    const response = await fetch(`${backend_url}/api/export`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    });
  
    if (response.status === 401) {
      Swal.fire({
        icon: 'error',
        title: 'Oops...',
        text: 'Session expired, please log in again!'
      });
      router.push('/login');
      return;
    }
  
    const data = await response.json();
    const folders = data.map(folder => {
      return {
        ...folder,
        files: folder.files.map(file => ({
          id: file.id,
          name: file.filename,
          uploadDate: new Date(file.timestamp).toLocaleString()
        }))
      };
    });
    setFolders(folders);
  };
  



  useEffect(() => {
    fetchExportedFiles();
  }, []);

  const handleDelete = async (index) => {
    const file = files[index];
    const response = await fetch(`${backend_url}/api/delexport/${file.id}`, {
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

  const handleViewOnMap = (index) => {
    console.log("view map clicked");
    const file = files[index];
    setMbtid(file.id);
    router.push("/");
  };

  return (
    <div>
      <StyledContainer component="main" maxWidth="md">
        <HeaderText component="h1" variant="h5">
          Your Uploaded Files
        </HeaderText>
        <FileTable folders={folders} handleDelete={handleDelete} handleViewOnMap={handleViewOnMap} />
      </StyledContainer>
    </div>
  );
};

const FileTable = ({ folders, handleDelete, handleViewOnMap }) => {
  return (
    <>
      {folders.map((folder) => (
        <div key={folder.id}>
          <Typography variant="h6" gutterBottom>
            Folder: {folder.name} - Created at: {new Date(folder.timestamp).toLocaleString()}
          </Typography>
          <TableContainer component={Paper} sx={{ marginBottom: "20px", maxHeight: "80vh", overflow: "auto" }}>
            <StyledTable aria-label="uploaded files table">
              <TableHead>
                <TableRow>
                  <TableCell>Filename</TableCell>
                  <TableCell align="right">Created Time</TableCell>
                  <TableCell align="right">Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {folder.files.map((file, index) => (
                  <TableRow key={index}>
                    <TableCell>{file.name}</TableCell>
                    <TableCell align="right">{new Date(file.timestamp).toLocaleString()}</TableCell>
                    <TableCell align="right">
                      <IconButton onClick={() => handleViewOnMap(index)}>
                        <MapIcon />
                        <Typography sx={{ marginLeft: "10px" }}>
                          View on Map
                        </Typography>
                      </IconButton>
                      <StyledIconButton onClick={() => handleDelete(index)}>
                        <DeleteIcon />
                        <Typography sx={{ marginLeft: "10px" }}>
                          Delete
                        </Typography>
                      </StyledIconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </StyledTable>
          </TableContainer>
        </div>
      ))}
    </>
  );
};


export default PreviousExport;