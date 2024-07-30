import React, { useEffect, useState, useContext, useRef } from "react";
import { useRouter } from "next/router";
import {
    TextField,
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
    Button,
} from "@mui/material";
import { styled } from "@mui/material/styles";
import DeleteIcon from "@mui/icons-material/Delete";
import { Box } from "@mui/system";
import Swal from "sweetalert2";
import SelectedLocationContext from "../contexts/SelectedLocationContext";
import LocationOnIcon from '@mui/icons-material/LocationOn';
import { backend_url } from "../utils/settings";
import UndoIcon from '@mui/icons-material/Undo';
import SelectedPolygonContext from "../contexts/SelectedPolygonContext";
import SelectedPolygonAreaContext from "../contexts/SelectedPolygonAreaContext.js";
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { useFolder } from "../contexts/FolderContext.js";
import { toast, ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import FetchTaskInfoContext from "../contexts/FetchTaskInfoContext.js";
import { polygon } from "@turf/turf";


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


const MyEdit = () => {

    const router = useRouter();

    const { setLocation } = useContext(SelectedLocationContext);
    const { selectedPolygons, setSelectedPolygons } = useContext(SelectedPolygonContext);
    const { selectedPolygonsArea, setSelectedPolygonsArea } = useContext(SelectedPolygonAreaContext);

    const { folderID, setFolderID } = useFolder();

    const { setShouldFetchTaskInfo } = useContext(FetchTaskInfoContext);

    const handleLocateOnMap = (option) => {
        if (option !== undefined && option !== null) {
            console.log(option);
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


    const handleUndoPolygonEdit = (index) => {
        // Clone the arrays before modifications to avoid side-effects
        const updatedPolygons = [...selectedPolygons];
        const updatedPolygonsArea = [...selectedPolygonsArea];

        // Check if the index is valid before trying to remove the item
        if (index >= 0 && index < updatedPolygons.length) {
            updatedPolygons.splice(index, 1);
            updatedPolygonsArea.splice(index, 1);

            // Update state with new arrays
            setSelectedPolygons(updatedPolygons);
            setSelectedPolygonsArea(updatedPolygonsArea);
        } else {
            console.error("Invalid index for undo operation");
        }
    };


    const toggleMarkers = async () => {
        try {
            const polygonPoints = selectedPolygons.map(polygon =>
                polygon.slice(1).map(point => ({
                    id: point.id,
                    served: point.served,
                    editedFile: Array.isArray(point.editedFile) ? point.editedFile : Array.from(point.editedFile) // Ensure editedFile is serialized correctly
                }))
            );

            console.log(selectedPolygonsArea);



            const requestBody = {
                marker: polygonPoints,
                polygonfeatures: selectedPolygonsArea,
                folderid: folderID
            };

            const response = await fetch(`${backend_url}/api/toggle-markers`, {
                method: "POST",
                credentials: "include", // Include cookies in the request
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(requestBody),
            });

            if (response.status === 401) {
                // Redirect the user to the login page or other unauthorized handling page
                Swal.fire({
                    icon: "error",
                    title: "Oops...",
                    text: "Session expired, please log in again!",
                });
                router.push("/login");
            }
            if (!response.ok) {
                // If the response status is not ok (not 200)
                throw new Error(`HTTP error! status: ${response.status}, ${response.statusText}`);
            }
            const data = await response.json();
            if (data) {
                toast.success("Your edit request has been successfully submitted");
                setSelectedPolygons([]);
                setSelectedPolygonsArea([]);
                setShouldFetchTaskInfo(true);

            }
        } catch (error) {
            console.error("Error:", error);
        }
    };



    return (
        <div>
            <StyledContainer component="main" maxWidth="md">
                <PolygonEditTable
                    polygons={selectedPolygons}
                    handleUndoPolygonEdit={handleUndoPolygonEdit}
                    handleLocateOnMap={handleLocateOnMap}
                />
                <Button
                    variant="contained"
                    color="primary"
                    onClick={toggleMarkers}
                    sx={{ marginTop: '20px' }}
                >
                    Submit Changes
                </Button>
            </StyledContainer>
        </div>

    );
};


const PolygonEditTable = ({ polygons, handleUndoPolygonEdit, handleLocateOnMap }) => {
    const [expandedPolygon, setExpandedPolygon] = useState(null);

    const toggleExpand = (polygonId) => {
        if (expandedPolygon === polygonId) {
            setExpandedPolygon(null);
        } else {
            setExpandedPolygon(polygonId);
        }
    };

    return (
        <div>
            <ToastContainer />
            <Typography variant="h6" sx={{ margin: "20px 0" }}>
                Bulk Edits
            </Typography>
            <TableContainer component={Paper} sx={{ marginBottom: "20px", maxHeight: "80vh", overflow: "auto" }}>
                <Table aria-label="polygon edit table">
                    <TableHead>
                        <TableRow>
                            <TableCell>Polygon ID</TableCell>
                            <TableCell></TableCell>
                            <TableCell align='right'>Action</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {polygons.map((polygonGroup, groupIndex) => (
                            <React.Fragment key={`polygon-group-${groupIndex}`}>
                                <TableRow key={`polygon-${groupIndex}`}>
                                    <TableCell>
                                        {polygonGroup[0].id}
                                    </TableCell>
                                    <TableCell>
                                        <IconButton onClick={() => toggleExpand(polygonGroup[0].id)}>
                                            {expandedPolygon === polygonGroup[0].id ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                                        </IconButton>
                                    </TableCell>
                                    <TableCell align="right">
                                        <IconButton onClick={() => handleUndoPolygonEdit(groupIndex)}>
                                            <UndoIcon />
                                        </IconButton>
                                    </TableCell>
                                </TableRow>
                                {expandedPolygon === polygonGroup[0].id && (
                                    <React.Fragment key={`expanded-${groupIndex}`}>
                                        <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                                            <TableCell>Location ID</TableCell>
                                            <TableCell>Address</TableCell>
                                            <TableCell></TableCell>
                                        </TableRow>
                                        {polygonGroup.slice(1).map((point, pointIndex) => (
                                            <TableRow key={`point-${groupIndex}-${pointIndex}`} sx={{ backgroundColor: '#f5f5f5' }}>
                                                <TableCell>
                                                    {point.id}
                                                </TableCell>
                                                <TableCell>
                                                    {point.address}
                                                </TableCell>
                                                <TableCell>
                                                    <IconButton onClick={() => handleLocateOnMap(point)}>
                                                        <LocationOnIcon />
                                                    </IconButton>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </React.Fragment>
                                )}
                            </React.Fragment>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </div>
    );
};



export default MyEdit;