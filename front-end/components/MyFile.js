import React, { useEffect, useState, useContext } from "react";
import { useRouter } from "next/router";
import {
  Typography,
  Container,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Switch,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from "@mui/material";
import Swal from "sweetalert2";
import DeleteIcon from "@mui/icons-material/Delete";
import LayerVisibilityContext from "../contexts/LayerVisibilityContext";
import SelectedLocationContext from "../contexts/SelectedLocationContext";
import LocationOnIcon from '@mui/icons-material/LocationOn';
import { backend_url } from "../utils/settings";
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { styled } from '@mui/material/styles';
import { useFolder } from '../contexts/FolderContext';
import { format } from "date-fns";
import EditLayerVisibilityContext from "../contexts/EditLayerVisibilityContext.js";
import { toast, ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import FetchTaskInfoContext from "../contexts/FetchTaskInfoContext.js";
import ReloadMapContext from "../contexts/ReloadMapContext.js";


const StyledContainer = styled(Container)(({ }) => ({
  zIndex: 1000,
  position: "relative",
  minWidth: "80%",
  maxHeight: "100vh",
  marginTop: "40px",
  overflow: "auto",
  padding: "20px" // Added padding to ensure content inside has enough space
}));

const StyledTypography = styled(Typography)(({ }) => ({
  marginBottom: "20px",
  marginTop: "20px",
}));

const StyledTable = styled(Table)(({ }) => ({
  minWidth: 650,
}));

const StyledIconButton = styled(IconButton)(({ }) => ({
  color: "#f44336", // Red color
  "&:hover": {
    color: "#d32f2f", // Darker red on hover
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

const DeleteConfirmationDialog = ({ open, onClose, onConfirm }) => (
  <Dialog
    open={open}
    onClose={onClose}
    aria-labelledby="delete-confirmation-dialog-title"
    aria-describedby="delete-confirmation-dialog-description"
  >
    <DialogTitle id="delete-confirmation-dialog-title">{"Confirm Delete"}</DialogTitle>
    <DialogContent>
      <DialogContentText id="delete-confirmation-dialog-description">
        Are you sure you want to delete the filing? This action cannot be undone.
      </DialogContentText>
    </DialogContent>
    <DialogActions>
      <Button onClick={onClose} color="primary">Cancel</Button>
      <Button onClick={onConfirm} color="primary" autoFocus>Delete</Button>
    </DialogActions>
  </Dialog>
);

const MyFile = () => {
  const [fabricFiles, setFabricFiles] = useState([]);
  const [networkDataFiles, setNetworkDataFiles] = useState([]);
  const [manualEditFiles, setManualEditFiles] = useState([]);
  const [folders, setFolders] = useState([]);
  const { folderID, setFolderID } = useFolder();
  const { setLayers } = useContext(LayerVisibilityContext);


  const { setLocation } = useContext(SelectedLocationContext);

  const { setShouldFetchTaskInfo } = useContext(FetchTaskInfoContext);

  const { setShouldReloadMap } = useContext(ReloadMapContext);

  const router = useRouter();

  const [dialogOpen, setDialogOpen] = useState(false);

  const handleDeleteFiling = () => {
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
  };

  const handleConfirmDelete = async () => {
    setDialogOpen(false);
    try {
      const response = await fetch(`${backend_url}/api/delfiling`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ folderID }), // Adjust the payload as needed
        credentials: "include",
      });


      // Assuming the API returns the updated list of files
      const data = await response.json();
      if (data.status === "success") {
        toast.success("Filing deleted successfully");
        setFolderID(-1);
        setShouldReloadMap(true);
        setFolders((prevFolders) => prevFolders.filter(folder => folder.folder_id !== folderID));
      }
      else {
        toast.error(data.message);
      }

    } catch (error) {
      toast.error("Error on our end. Please try again later");
    }
  };

  const handleRegenerateMap = async () => {
    try {
      const response = await fetch(`${backend_url}/api/regenerate_map`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ folderID }), // Adjust the payload as needed
        credentials: "include",
      });


      // Assuming the API returns the updated list of files
      const data = await response.json();
      if (data.status === "success") {
        toast.success("Map regeneration request submitted");
        setShouldReloadMap(true);
      }
      else {
        toast.error(data.message);
      }

    } catch (error) {
      toast.error("Error on our end. Please try again later");
    }
  };

  const handleLocateOnMap = (option) => {
    if (option !== undefined && option !== null) {
      setLocation({
        latitude: option.latitude,
        longitude: option.longitude,
        zoomlevel: 12,
      });
    }
    else {
      setLocation(null);
    }
  }



  const fetchFolders = async () => {
    try {
      const response = await fetch(`${backend_url}/api/folders-with-deadlines`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      });

      if (response.status === 401) {
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: "Session expired, please log in again!",
        });
        router.push("/login");
        return;
      }

      const data = await response.json();
      setFolders(data);

    } catch (error) {
      console.error("Error fetching folders:", error);
    }
  };


  const fetchFiles = async (folderIdentity) => {
    setFabricFiles([]);
    setNetworkDataFiles([]);
    if (folderIdentity === -1) {
      return;
    }
    const response = await fetch(`${backend_url}/api/files?folder_ID=${folderIdentity}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include", // Include cookies in the request
    });

    if (response.status === 401) {
      Swal.fire({
        icon: "error",
        title: "Oops...",
        text: "Session expired, please log in again!",
      });
      // Redirect to login page
      router.push("/login");
      return;
    }

    const data = await response.json();
    if (!Array.isArray(data)) {
      console.error("Error: Expected data to be an array, but received:", data);
      return;
    }

    if (!data || data.length === 0) {
      console.log("Error: Empty response received from server");
    } else {
      data.forEach((file) => {
        const formattedFile = {
          id: file.id,
          name: file.name,
          uploadDate: new Date(file.timestamp).toLocaleString(),
          type: file.type,
          kmlData: file.kml_data,
        };
        if (file.name.endsWith(".csv")) {
          setFabricFiles((prevFiles) => [...prevFiles, formattedFile]);
        } else if (file.name.endsWith(".kml") || file.name.endsWith(".geojson")) {
          setNetworkDataFiles((prevFiles) => [...prevFiles, formattedFile]);
          setLayers((prevLayers) => ({
            ...prevLayers,
            [file.name]: true, // Set the visibility of the layer to true
          }));
        }
      });
    }
  };


  const fetchEditFiles = async (folderIdentity) => {
    setManualEditFiles([]);
    if (folderIdentity === -1) {
      return;
    }
    const response = await fetch(`${backend_url}/api/editfiles?folder_ID=${folderIdentity}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include", // Include cookies in the request
    });

    if (response.status === 401) {
      Swal.fire({
        icon: "error",
        title: "Oops...",
        text: "Session expired, please log in again!",
      });
      // Redirect to login page
      router.push("/login");
      return;
    }

    const data = await response.json();
    if (!Array.isArray(data)) {
      console.error("Error: Expected data to be an array, but received:", data);
      return;
    }

    if (!data || data.length === 0) {
      console.log("Error: Empty response received from server");
    } else {
      data.forEach((file) => {
        const formattedFile = {
          id: file.id,
          name: file.name,
          uploadDate: new Date(file.timestamp).toLocaleString(),
          associated_files: file.associated_files,
        };

        setManualEditFiles((prevFiles) => [...prevFiles, formattedFile]);

      });
    }
  };

  useEffect(() => {
    fetchFolders();
  }, []);

  useEffect(() => {

    fetchFiles(folderID);
    fetchEditFiles(folderID);
  }, [folderID]);



  const handleDeadlineSelect = (newFolderID) => {
    setFolderID(newFolderID);
    setShouldReloadMap(true);
  }


  const handleDeleteCheckedFiles = async () => {
    try {
      const fileIdsToDelete = [
        ...fabricFiles,
        ...networkDataFiles
      ]
        .filter((file) => file.checked)
        .map((file) => file.id);

      const editFileIdsToDelete = manualEditFiles
        .filter((file) => file.checked)
        .map((file) => file.id);


      if (fileIdsToDelete.length === 0 && editFileIdsToDelete.length === 0) {
        toast.error("Please check the file you want to delete");
        return;
      }

      const response = await fetch(`${backend_url}/api/delfiles`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({ file_ids: fileIdsToDelete, editfile_ids: editFileIdsToDelete }),
      });

      if (response.status === 401) {
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: "Session expired, please log in again!",
        });
        router.push("/login");
        return;
      }

      const data = await response.json();

      if (data.status === "success") {
        toast.success("Your deletion request has been successfully submitted");
        fetchFiles(folderID);
        fetchEditFiles(folderID);
        setShouldFetchTaskInfo(true);
      } else {
        toast.error(data.message);
      }
    } catch (error) {
      console.error("Error:", error);
      toast.error(error);
    }
  };


  return (
    <div>
      <ToastContainer />
      <StyledContainer component="main" maxWidth="md">
        <FormControl style={{ width: '250px' }}>
          <InputLabel id="filing-select-label">You are working on filing for deadline:</InputLabel>
          <Select
            labelId="filing-select-label"
            id="filing-select"
            value={folderID}
            label="You are working on Filing for Deadline:"
            onChange={(e) => handleDeadlineSelect(e.target.value)}
          >
            <MenuItem value={-1}><em>Select Filing</em></MenuItem>
            {folders.map((folder) => (
              <MenuItem key={folder.deadline} value={folder.folder_id}>
                {format(new Date(folder.deadline), 'MMMM yyyy')}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button variant="contained" color="error" onClick={handleDeleteCheckedFiles} sx={{ marginLeft: '30px' }}>
          Delete Checked Files
        </Button>
        {/* Fabric Files Table */}
        <StyledTypography component="h2" variant="h6">
          Fabric Files
        </StyledTypography>
        <FileTable
          files={fabricFiles}
          setFiles={setFabricFiles}
          showSwitch={false}
        />

        {/* Network Data Files Table */}
        <StyledTypography component="h2" variant="h6">
          Network Data Files
        </StyledTypography>
        <FileTable
          files={networkDataFiles}
          setFiles={setNetworkDataFiles}
          showSwitch={true}
        />

        {/* Manual Edit Files Table */}
        <StyledTypography component="h2" variant="h6">
          Manual Edits
        </StyledTypography>
        <ManualEditFilesTable
          files={manualEditFiles}
          handleLocateOnMap={handleLocateOnMap}
          setFiles={setManualEditFiles}
        />
        <Button variant="contained" color="error" onClick={handleDeleteFiling} sx={{ marginTop: '20px' }}>
          Delete this Filing
        </Button>
        <Button variant="contained" color="secondary" onClick={handleRegenerateMap} sx={{ marginTop: '20px', marginLeft: '10px' }}>
          Regenerate map
        </Button>
      </StyledContainer>

      <DeleteConfirmationDialog
        open={dialogOpen}
        onClose={handleCloseDialog}
        onConfirm={handleConfirmDelete}
      />
    </div>
  );
};

const FileTable = ({
  files,
  setFiles,
  showSwitch,
}) => {
  const { setLayers } = useContext(LayerVisibilityContext);
  const [checked, setChecked] = useState([]);

  useEffect(() => {
    setChecked(new Array(files.length).fill(true));
  }, [files]);

  const handleToggle = (i) => () => {
    const newChecked = [...checked];
    newChecked[i] = !newChecked[i];
    setChecked(newChecked);

    setLayers((prevLayers) => ({
      ...prevLayers,
      [files[i].name]: newChecked[i],
    }));
  };

  const handleCheck = (i) => () => {
    const updatedFiles = [...files];
    updatedFiles[i].checked = !updatedFiles[i].checked;
    setFiles(updatedFiles);
  };

  if (checked.length !== files.length) {
    return null;
  }

  return (
    <StyledTable aria-label="file table">
      <TableHead>
        <TableRow>
          <TableCell>Filename</TableCell>
          <TableCell>Created Time</TableCell>
          <TableCell align="right">Type</TableCell>
          {showSwitch && <TableCell align="right">Show on Map</TableCell>}
          <TableCell align="right">Check</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {files.map((file, index) => (
          <TableRow key={index}>
            <TableCell component="th" scope="row">
              {file.name}
            </TableCell>
            <TableCell>{file.uploadDate}</TableCell>
            <TableCell align="right">{file.type}</TableCell>
            {showSwitch && (
              <TableCell align="right">
                <IOSSwitch
                  sx={{ m: 1 }}
                  checked={checked[index]}
                  onChange={handleToggle(index)}
                  name="showOnMapSwitch"
                  inputProps={{ "aria-label": "secondary checkbox" }}
                />
              </TableCell>
            )}
            <TableCell align="right">
              <Checkbox
                checked={file.checked || false}
                onChange={handleCheck(index)}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </StyledTable>
  );
};

const ManualEditFilesTable = ({
  files,
  handleLocateOnMap,
  setFiles
}) => {
  const [checked, setChecked] = useState([]);
  const { setEditLayers } = useContext(EditLayerVisibilityContext);

  useEffect(() => {
    setChecked(new Array(files.length).fill(false));
  }, [files]);

  const fetchGeoJSONCentroid = (editfile_id) => {
    fetch(`${backend_url}/api/get-edit-geojson-centroid/${editfile_id}`, {
      method: "GET",
      credentials: "include",
    })
      .then(response => {
        if (!response.ok) {
          throw new Error('Failed to fetch coverage data');
        }
        return response.json();
      })
      .then(data => {
        handleLocateOnMap({
          latitude: data.latitude,
          longitude: data.longitude
        })
      })
      .catch((error) => {
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: error.message,
        });
      });
  };

  const handleToggle = (i) => () => {
    const newChecked = [...checked];
    newChecked[i] = !newChecked[i];
    setChecked(newChecked);

    setEditLayers((prevLayers) => {
      const fileId = files[i].id;
      if (newChecked[i]) {
        fetchGeoJSONCentroid(fileId);
        return [...prevLayers, fileId];
      } else {
        return prevLayers.filter(layer => layer !== fileId);
      }
    });
  };

  const handleCheck = (i) => () => {
    const updatedFiles = [...files];
    updatedFiles[i].checked = !updatedFiles[i].checked;
    setFiles(updatedFiles);
  };

  return (
    <StyledTable>
      <TableHead>
        <TableRow>
          <TableCell>Filename</TableCell>
          <TableCell>Created Time</TableCell>
          <TableCell>Edit On</TableCell>
          <TableCell align="right">Locate On Map</TableCell>
          <TableCell align="right">Check</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {files.map((file, index) => (
          <React.Fragment key={index}>
            <TableRow>
              <TableCell>{file.name}</TableCell>
              <TableCell>{file.uploadDate}</TableCell>
              <TableCell>{file.associated_files.join(', ')}</TableCell>
              <TableCell align="right">
                <IOSSwitch
                  sx={{ m: 1 }}
                  checked={checked[index]}
                  onChange={handleToggle(index)}
                  name="showOnMapSwitch"
                  inputProps={{ "aria-label": "secondary checkbox" }}
                />
              </TableCell>
              <TableCell align="right">
                <Checkbox
                  checked={file.checked || false}
                  onChange={handleCheck(index)}
                />
              </TableCell>
            </TableRow>
          </React.Fragment>
        ))}
      </TableBody>
    </StyledTable>
  );
};

export default MyFile;