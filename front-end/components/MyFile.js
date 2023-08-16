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
} from "@mui/material";
import Swal from "sweetalert2";
import DeleteIcon from "@mui/icons-material/Delete";
import LayerVisibilityContext from "../contexts/LayerVisibilityContext";
import LoadingEffect from "./LoadingEffect";
import SelectedLocationContext from "../contexts/SelectedLocationContext";
import LocationOnIcon from '@mui/icons-material/LocationOn';
import { backend_url } from "../utils/settings";
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { styled } from '@mui/material/styles';


// useStyles is replaced by the styled utility in v5
const StyledContainer = styled(Container)(({ }) => ({
  zIndex: 1000,
  position: "relative",
  minWidth: "80%",
  height: "90vh",
  marginTop: "20px",
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

const MyFile = () => {
  const [fabricFiles, setFabricFiles] = useState([]);
  const [networkDataFiles, setNetworkDataFiles] = useState([]);
  const [manualEditFiles, setManualEditFiles] = useState([]);

  const { setLayers } = useContext(LayerVisibilityContext);

  const [isLoading, setIsLoading] = useState(false);
  const [isDataReady, setIsDataReady] = useState(false);
  const loadingTimeInMs = 3.5 * 60 * 1000;

  const { setLocation } = useContext(SelectedLocationContext);

  const router = useRouter();

  const handleLocateOnMap = (option) => {
    if (option !== undefined && option !== null) {
      setLocation({
        latitude: option.latitude,
        longitude: option.longitude,
        zoomlevel: 16,
      });
    }
    else {
      setLocation(null);
    }
  }

  const fetchFiles = async () => {
    const response = await fetch(`${backend_url}/api/files`, {
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
        console.log(file);
        const formattedFile = {
          id: file.id,
          name: file.name,
          uploadDate: new Date(file.timestamp).toLocaleString(),
          type: file.type,
          kmlData: file.kml_data,
        };
        if (file.name.endsWith(".csv")) {
          setFabricFiles((prevFiles) => [...prevFiles, formattedFile]);
        } else if (file.name.endsWith(".kml")) {
          setNetworkDataFiles((prevFiles) => [...prevFiles, formattedFile]);
          setLayers((prevLayers) => ({
            ...prevLayers,
            [file.name]: true, // Set the visibility of the layer to true
          }));
        } else if (file.name.endsWith("/")) {
          setManualEditFiles((prevFiles) => [...prevFiles, formattedFile]);
        }
      });
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  const handleDelete = async (id, setFiles) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${backend_url}/api/delfiles/${id}`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include", // Include cookies in the request
      });

      if (response.status === 401) {
        setIsLoading(false);
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: "Session expired, please log in again!",
        });
        // Redirect to login page
        router.push("/login");
        return;
      }

      if (!response.ok) {
        // If the response status is not ok (not 200)
        throw new Error(
          `HTTP error! status: ${response.status}, ${response.statusText}`
        );
      }

      setFiles((prevFiles) => prevFiles.filter((file) => file.id !== id));
      setIsDataReady(true);
      setIsLoading(false);
      setTimeout(() => {
        setIsDataReady(false);
      }, 5000);
      router.reload();
    } catch (error) {
      setIsLoading(false);
      console.error("An error occurred:", error);
    }
  };

  return (
    <div>
      <div style={{ position: 'fixed', zIndex: 10000 }}>
        {(isLoading || isDataReady) && (
          <LoadingEffect
            isLoading={isLoading}
            loadingTimeInMs={loadingTimeInMs}
          />
        )}
      </div>
      <StyledContainer component="main" maxWidth="md">
        <StyledTypography component="h1" variant="h5">
          Your Uploaded Files
        </StyledTypography>
        {/* Fabric Files Table */}
        <StyledTypography component="h2" variant="h6">
          Fabric Files
        </StyledTypography>
        <FileTable
          files={fabricFiles}
          handleDelete={handleDelete}
          setFiles={setFabricFiles}
          showSwitch={false}
          showDelete={true}
        />

        {/* Network Data Files Table */}
        <StyledTypography component="h2" variant="h6">
          Network Data Files
        </StyledTypography>
        <FileTable
          files={networkDataFiles}
          handleDelete={handleDelete}
          setFiles={setNetworkDataFiles}
          showSwitch={true}
          showDelete={true}
        />

        {/* Manual Edit Files Table */}
        <StyledTypography component="h2" variant="h6">
          Manual Edits
        </StyledTypography>
        <ManualEditFilesTable
          files={manualEditFiles}
          handleLocateOnMap={handleLocateOnMap}
          handleDelete={handleDelete}
        />
      </StyledContainer>
    </div>
  );
};

const FileTable = ({
  files,
  handleDelete,
  setFiles,
  showSwitch,
  showDelete
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

    // Update the layers visibility state
    setLayers((prevLayers) => ({
      ...prevLayers,
      [files[i].name]: newChecked[i],
    }));
  };

  if (checked.length !== files.length) {
    return null; // or return a loading spinner
  }

  return (
    <TableContainer component={Paper}>
      <StyledTable aria-label="file table">
        <TableHead>
          <TableRow>
            <TableCell>Filename</TableCell>
            <TableCell>Created Time</TableCell>
            <TableCell align="right">Type</TableCell>
            {showSwitch && <TableCell align="right">Show on Map</TableCell>}
            {showDelete && <TableCell align="right">Action</TableCell>}
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
              {showDelete && (
                <TableCell align="right">
                  <StyledIconButton
                    onClick={() => handleDelete(file.id, setFiles)}
                  >
                    <DeleteIcon />
                    <Typography sx={{ marginLeft: "10px" }}>
                      Delete File
                    </Typography>
                  </StyledIconButton>
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </StyledTable>
    </TableContainer>
  );
};

const ManualEditFilesTable = ({
  files,
  handleLocateOnMap,
  handleDelete,
}) => {
  const [expandedRows, setExpandedRows] = React.useState([]);

  const toggleRowExpansion = (fileId) => {
    setExpandedRows(prev => {
      if (prev.includes(fileId)) {
        return prev.filter(id => id !== fileId);
      } else {
        return [...prev, fileId];
      }
    });
  };

  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableCell>Filename</TableCell>
          <TableCell>Created Time</TableCell>
          <TableCell>Type</TableCell>
          <TableCell align="right">Show All Points</TableCell>
          <TableCell align="right">Action</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {files.map((file, index) => (
          <React.Fragment key={index}>
            <TableRow>
              <TableCell>{file.name}</TableCell>
              <TableCell>{file.timestamp}</TableCell>
              <TableCell>{file.type}</TableCell>

              <TableCell align="right">
                <IconButton
                  onClick={() => toggleRowExpansion(file.id)}
                >
                  <ExpandMoreIcon />
                </IconButton>
              </TableCell>

              <TableCell align="right">
                <StyledIconButton
                  onClick={() => handleDelete(file.id, setFiles)}
                >
                  <DeleteIcon />
                  <Typography sx={{ marginLeft: "10px" }}>
                    Delete File
                  </Typography>
                </StyledIconButton>
              </TableCell>

            </TableRow>
            {file.kmlData && expandedRows.includes(file.id) && (
              <TableRow>
                <TableCell colSpan={4}>
                  {file.kmlData.map((data, dataIndex) => (
                    <div key={dataIndex} style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ marginRight: '16px' }}>{data.address}</span>
                      <IconButton
                        onClick={() => handleLocateOnMap({
                          latitude: data.latitude,
                          longitude: data.longitude
                        })}
                      >
                        <LocationOnIcon />
                      </IconButton>
                    </div>
                  ))}
                </TableCell>
              </TableRow>
            )}
          </React.Fragment>
        ))}
      </TableBody>
    </Table>
  );
};

export default MyFile;