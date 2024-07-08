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
import LoadingEffect from "./LoadingEffect";
import SelectedLocationContext from "../contexts/SelectedLocationContext";
import LocationOnIcon from '@mui/icons-material/LocationOn';
import { backend_url } from "../utils/settings";
import UndoIcon from '@mui/icons-material/Undo';
import SelectedPointsContext from "../contexts/SelectedPointsContext";
import SelectedPolygonContext from "../contexts/SelectedPolygonContext";
import SelectedPolygonAreaContext from "../contexts/SelectedPolygonAreaContext.js";
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import {useFolder} from "../contexts/FolderContext.js";


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


const MyEdit = () => {

    const router = useRouter();

    const [isLoading, setIsLoading] = useState(false);
    const [isDataReady, setIsDataReady] = useState(false);
    const loadingTimeInMs = 3.5 * 60 * 1000;

    const { setLocation } = useContext(SelectedLocationContext);
    const { selectedPoints, setSelectedPoints } = useContext(SelectedPointsContext);
    const { selectedPolygons, setSelectedPolygons } = useContext(SelectedPolygonContext);
    const { selectedPolygonsArea, setSelectedPolygonsArea } = useContext(SelectedPolygonAreaContext);

    const {folderID, setFolderID} = useFolder();

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

    const handleUndoSingleEdit = (index) => {
        // Create a new array without the item at the given index
        const updatedPoints = [...selectedPoints];
        updatedPoints.splice(index, 1);
        setSelectedPoints(updatedPoints);
    };

    const handleUndoPolygonEdit = (index) => {
        const updatedPolygons = [...selectedPolygons];
        updatedPolygons.splice(index, 1);
        setSelectedPolygons(updatedPolygons);

        const updatedPolygonsArea = [...selectedPolygonsArea];
        updatedPolygons.splice(index, 1);
        setSelectedPolygonsArea(updatedPolygonsArea);
    };

    const handleUndoSinglePointWithinPolygon = (polygonIndex, pointIndex) => {
        // Clone the current state of polygons
        const updatedPolygons = [...selectedPolygons];

        // Check if the polygon exists
        if (updatedPolygons[polygonIndex]) {
            // Clone the polygon to avoid direct mutation
            const updatedPolygon = [...updatedPolygons[polygonIndex]];

            // Adjust the point index by 1 to account for the ID at the first position
            const adjustedPointIndex = pointIndex + 1;

            // Check if the point exists and remove it
            if (updatedPolygon[adjustedPointIndex]) {
                updatedPolygon.splice(adjustedPointIndex, 1);

                // If only the ID is left in the polygon, remove the entire polygon
                if (updatedPolygon.length <= 1) {
                    updatedPolygons.splice(polygonIndex, 1);
                } else {
                    // Otherwise, update the polygon with the point removed
                    updatedPolygons[polygonIndex] = updatedPolygon;
                }

                // Update the state with the modified polygons array
                setSelectedPolygons(updatedPolygons);
            } else {
                console.error("Invalid point index");
            }
        } else {
            console.error("Invalid polygon index");
        }
    };

    const toggleMarkers = async () => {
        setIsLoading(true);
        try {
            const polygonPoints = selectedPolygons.flatMap(polygon => 
                polygon.slice(1)  // Skip the first element (timestamp) and take the rest (points)
            );
    
            // Merge points from selectedPoints and polygonPoints
            const combinedPoints = [...selectedPoints, ...polygonPoints].map((point) => ({
                id: point.id,
                served: point.served,
            }));
    
            const requestBody = {
                marker: combinedPoints,
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
                setIsLoading(false);
                // Redirect the user to the login page or other unauthorized handling page
                Swal.fire({
                    icon: "error",
                    title: "Oops...",
                    text: "Session expired, please log in again!",
                });
                router.push("/login");
            }
            if (!response.ok) {
                setIsLoading(false);
                // If the response status is not ok (not 200)
                throw new Error(`HTTP error! status: ${response.status}, ${response.statusText}`);
            }
            const data = await response.json();
            if (data) {
                const intervalId = setInterval(() => {
                    console.log(data.task_id);
                    fetch(`${backend_url}/api/status/${data.task_id}`)
                        .then((response) => response.json())
                        .then((status) => {
                            if (status.state !== "PENDING") {
                                clearInterval(intervalId);
                                setIsDataReady(true);
                                setIsLoading(false);
                                setTimeout(() => {
                                    setIsDataReady(false);
                                    router.reload();
                                }, 5000);
                            }
                        });
                }, 5000);
            }
        } catch (error) {
            console.error("Error:", error);
            setIsLoading(false);
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
                <PolygonEditTable
                    polygons={selectedPolygons}
                    handleUndoPolygonEdit={handleUndoPolygonEdit}
                    handleLocateOnMap={handleLocateOnMap}
                    handleUndoSinglePointWithinPolygon={handleUndoSinglePointWithinPolygon}
                />
                <FileTable
                    files={selectedPoints}
                    handleUndoSingleEdit={handleUndoSingleEdit}
                    handleLocateOnMap={handleLocateOnMap}
                />
            </StyledContainer>
            <div style={{ marginTop: '20px', marginLeft: '20px' }}>
                <Button
                    variant="contained"
                    color="primary"
                    onClick={toggleMarkers}
                >
                    Submit Changes
                </Button>
            </div>
        </div>

    );
};


const FileTable = ({ files, handleUndoSingleEdit, handleLocateOnMap }) => {

    return (
        <div>
            <Typography variant="h6" sx={{ margin: "20px 0" }}>
                Single Point Edits
            </Typography>
            <TableContainer component={Paper} sx={{ marginBottom: "20px", maxHeight: "80vh", overflow: "auto" }}>
                <StyledTable aria-label="single point table">
                    <TableHead>
                        <TableRow>
                            <TableCell>Location ID</TableCell>
                            <TableCell>Address</TableCell>
                            <TableCell></TableCell>
                            <TableCell align='right'></TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {files.map((file, index) => (
                            <TableRow key={index}>
                                <TableCell>{file.id}</TableCell>
                                <TableCell>{file.address}</TableCell>
                                <TableCell>
                                    <IconButton
                                        onClick={() => handleLocateOnMap(file)}
                                    >
                                        <LocationOnIcon />

                                    </IconButton>
                                </TableCell>
                                <TableCell align="right">
                                    <StyledIconButton
                                        onClick={() => handleUndoSingleEdit(index)}
                                    >
                                        <UndoIcon />
                                    </StyledIconButton>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </StyledTable>
            </TableContainer>
        </div>
    );
};


const PolygonEditTable = ({ polygons, handleUndoPolygonEdit, handleLocateOnMap, handleUndoSinglePointWithinPolygon }) => {
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
                            <>
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
                                        <StyledIconButton onClick={() => handleUndoPolygonEdit(groupIndex)}>
                                            <UndoIcon />
                                        </StyledIconButton>
                                    </TableCell>
                                </TableRow>
                                {expandedPolygon === polygonGroup[0].id && (
                                    <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                                        <TableCell>Location ID</TableCell>
                                        <TableCell>Address</TableCell>
                                        <TableCell></TableCell>
                                        <TableCell align='right'></TableCell>
                                    </TableRow>
                                )}
                                {expandedPolygon === polygonGroup[0].id && polygonGroup.slice(1).map((point, pointIndex) => (
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
                                        <TableCell align="right">
                                            <StyledIconButton onClick={() => handleUndoSinglePointWithinPolygon(groupIndex, pointIndex)}>
                                                <UndoIcon />
                                            </StyledIconButton>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </div>
    );
};



export default MyEdit;