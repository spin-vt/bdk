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
import MbtilesContext from "../contexts/MbtilesContext";

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
    const { mbtid } = useContext(MbtilesContext);

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

    const toggleMarkers = async () => {
        setIsLoading(true);
        try {
            const selectedMarkerIds = [];
            selectedPoints.forEach((marker) => {
                selectedMarkerIds.push({ id: marker.id, served: marker.served });
            });
            const response = await fetch(`${backend_url}/toggle-markers`, {
                method: "POST",
                credentials: "include", // Include cookies in the request
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(selectedMarkerIds),
            })

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
                    fetch(`${backend_url}/status/${data.task_id}`)
                        .then((response) => response.json())
                        .then((status) => {
                            if (status.state !== "PENDING") {
                                clearInterval(intervalId);
                                setIsDataReady(true);
                                setIsLoading(false);
                                setTimeout(() => {
                                    setIsDataReady(false);
                                    router.reload();
                                }, 8000);
                            }
                        });
                }, 5000);
            }
        } catch (error) {
            console.error("Error:", error);
            setIsLoading(false);
        }
    };




    // const doneWithChanges = () => {
    //     setIsLoading(true);
    //     const selectedMarkerIds = [];
    //     selectedPoints.forEach((marker) => {
    //         selectedMarkerIds.push({ id: marker.id, served: marker.served });
    //     });

    //     // Send request to server to change the selected markers to served
    //     toggleMarkers(selectedMarkerIds).finally(() => {

    //         setIsDataReady(true);
    //         setIsLoading(false);

    //         setTimeout(() => {
    //             setIsDataReady(false); // This will be executed 15 seconds after setIsLoading(false)
    //         }, 5000);
    //         setSelectedPoints([]);
    //         router.reload();
    //     });
    // };


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
                <HeaderText component="h1" variant="h5">
                    Your Edits
                </HeaderText>
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
        <TableContainer component={Paper} sx={{ marginBottom: "20px", maxHeight: "80vh", overflow: "auto" }}>
            <StyledTable aria-label="single point table">
                <TableHead>
                    <TableRow>
                        <TableCell>Locate on Map</TableCell>
                        <TableCell>Address</TableCell>
                        <TableCell align='right'>Action</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {files.map((file, index) => (
                        <TableRow key={index}>
                            <TableCell>
                                <IconButton
                                    onClick={() => handleLocateOnMap(file)}
                                >
                                    <LocationOnIcon />

                                </IconButton>
                            </TableCell>
                            <TableCell>{file.address}</TableCell>
                            <TableCell align="right">
                                <StyledIconButton
                                    onClick={() => handleUndoSingleEdit(index)}
                                >
                                    <UndoIcon />
                                    <Typography sx={{ marginLeft: "10px" }}>
                                        Undo Point
                                    </Typography>
                                </StyledIconButton>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </StyledTable>
        </TableContainer>
    );
};

export default MyEdit;