import React, { useEffect, useState, useContext } from "react";
import { useRouter } from "next/router";
import { Typography, Container, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, IconButton } from "@mui/material";
import { styled } from "@mui/material/styles";
import DeleteIcon from "@mui/icons-material/Delete";
import MapIcon from "@mui/icons-material/Map";
import Swal from "sweetalert2";
import { backend_url } from "../utils/settings";
import dynamic from 'next/dynamic';
import Navbar from '../components/Navbar';
import EditMapContext from "../contexts/EditMapContext";
import Modal from '@mui/material/Modal';
import { Box } from '@mui/system';
import CloseIcon from '@mui/icons-material/Close';
import EditIcon from '@mui/icons-material/Edit';
import DownloadIcon from '@mui/icons-material/Download';
import {useFolder} from "../contexts/FolderContext.js";
import { toast, ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import ReloadMapContext from "../contexts/ReloadMapContext.js";


const Minimap = dynamic(
  () => import('../components/Minimap'),
  { ssr: false }
);

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

  const [filesByPeriod, setFilesByPeriod] = useState({});
  const router = useRouter();


  const { setEditingMap } = useContext(EditMapContext);

  const [viewonlymapid, setViewonlymapid] = useState(null);

  const [open, setOpen] = useState(false);

  const handleOpen = () => setOpen(true);
  const handleClose = () => setOpen(false);

  const {folderID, setFolderID} = useFolder();

  const { setShouldReloadMap } = useContext(ReloadMapContext);
  const fetchExportedFiles = async () => {
    try {
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

      if (!response.ok) {
        throw new Error(data.message || 'Failed to fetch exported files');
      }
      setFilesByPeriod(groupFilesByPeriod(data));
    } catch (error) {
      console.error(error);
      Swal.fire({
        icon: 'error',
        title: 'Error',
        text: 'Failed to fetch exported files.'
      });
    }
  };


  const groupFilesByPeriod = (files) => {
    return files.reduce((acc, file) => {
      const fileDate = new Date(file.timestamp);
      const year = fileDate.getFullYear();
      const startDate1 = new Date(year, 2, 16);
      const endDate1 = new Date(year, 8, 15);
      const startDate2 = new Date(year, 8, 16);
      const endDate2 = new Date(year + 1, 2, 15);

      let period = "";
      if (fileDate >= startDate1 && fileDate <= endDate1) {
        period = `${year} March 16 - ${year} Sep 15`;
      } else if (fileDate >= startDate2 && fileDate <= endDate2) {
        period = `${year} Sep 16 - ${year + 1} Mar 15`;
      }

      if (!acc[period]) {
        acc[period] = [];
      }
      acc[period].push(file);
      return acc;
    }, {});
  };




  useEffect(() => {
    fetchExportedFiles();
  }, []);

  const handleDelete = async (period, fileIndex) => {
    try {
      const file = filesByPeriod[period][fileIndex];
      const response = await fetch(`${backend_url}/api/delexport/${file.id}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });

      const data = await response.json();
      if (data.status === "success") {

      const newFilesByPeriod = { ...filesByPeriod };
      newFilesByPeriod[period].splice(fileIndex, 1);
      setFilesByPeriod(newFilesByPeriod);
      }
      else {
        toast.error(data.message);
      }
    } catch (error) {
      toast.error("Error on server side, please try again later");
    }
  };


  const handleDownload = async (period, fileIndex) => {
    try {
      const file = filesByPeriod[period][fileIndex];
      const response = await fetch(`${backend_url}/api/downloadexport/${file.id}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to download report');
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.name || 'download.csv'; // Use the file's name or a default
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();

    } catch (error) {
      console.error(error);
      Swal.fire({
        icon: 'error',
        title: 'Error',
        text: 'Failed to delete the report. Please try again.'
      });
    }
  };


  const handleEditMap = (period, fileIndex) => {
    const file = filesByPeriod[period][fileIndex];
    setFolderID(file.folder_id);
    setEditingMap(true);
    setShouldReloadMap(true);
    router.push("/");
  };

  const handleViewOnMap = (period, fileIndex) => {
    const file = filesByPeriod[period][fileIndex];
    setViewonlymapid(file.folder_id);
    handleOpen();
  };


  return (
    <div>
      <Navbar />
      <ToastContainer />
      <StyledContainer component="main" maxWidth="md">
        <HeaderText component="h1" variant="h5">
          Your Previous Exported Filings
        </HeaderText>
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
            <IconButton sx={{ backgroundColor: '#f76d9e' }} onClick={handleClose}><Typography>Close Map</Typography><CloseIcon /></IconButton>
            <Minimap id={viewonlymapid} />
          </Box>
        </Modal>
        <FileTable filesByPeriod={filesByPeriod} handleDelete={handleDelete} handleViewOnMap={handleViewOnMap} handleEditMap={handleEditMap} handleDownload={handleDownload} />
      </StyledContainer>
    </div>
  );
};

const FileTable = ({ filesByPeriod, handleDelete, handleViewOnMap, handleEditMap, handleDownload }) => {
  return (
    <>
      {Object.keys(filesByPeriod).map(period => (
        <div key={period}>
          <Typography variant="h6" gutterBottom>
            {period}
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
                {filesByPeriod[period].map((file, fileIndex) => (
                  <TableRow key={fileIndex}>
                    <TableCell>{file.name}</TableCell>
                    <TableCell align="right">{new Date(file.timestamp).toLocaleString()}</TableCell>
                    <TableCell align="right">
                      <StyledIconButton onClick={() => handleViewOnMap(period, fileIndex)}>
                        <MapIcon />
                        <Typography sx={{ marginLeft: "10px" }}>
                          View
                        </Typography>
                      </StyledIconButton>
                      <StyledIconButton onClick={() => handleEditMap(period, fileIndex)}>
                        <EditIcon />
                        <Typography sx={{ marginLeft: '10px' }}>
                          Edit
                        </Typography>
                      </StyledIconButton>
                      <StyledIconButton onClick={() => handleDownload(period, fileIndex)}>
                        <DownloadIcon />
                        <Typography sx={{ marginLeft: "10px" }}>
                          Download
                        </Typography>
                      </StyledIconButton>
                      <StyledIconButton onClick={() => handleDelete(period, fileIndex)}>
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