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
    Grid,
    Collapse,
    Button
} from "@material-ui/core";
import { makeStyles, useTheme } from "@material-ui/core/styles";
import Swal from "sweetalert2";
import DeleteIcon from "@mui/icons-material/Delete";
import { Box } from "@mui/system";
import { Switch, FormControlLabel } from "@material-ui/core";
import { styled } from "@mui/material/styles";
import LoadingEffect from "./LoadingEffect";
import SelectedLocationContext from "../contexts/SelectedLocationContext";
import LocationOnIcon from '@mui/icons-material/LocationOn';
import { backend_url } from "../utils/settings";
import UndoIcon from '@mui/icons-material/Undo';
import SelectedPointsContext from "../contexts/SelectedPointsContext";

const useStyles = makeStyles((theme) => ({
    headertext: {
        marginBottom: "20px",
        marginTop: "20px",
    },
    table: {
        minWidth: 650,
    },
    container: {
        zIndex: 1000,
        position: "relative",
        minWidth: "80%",
        height: "90vh",
        marginTop: "20px",
    },
    deleteButton: {
        color: "#f44336", // Red color
        "&:hover": {
            color: "#d32f2f", // Darker red on hover
        },
    },
}));


const MyEdit = () => {
    const classes = useStyles();

    const router = useRouter();

    const [isLoading, setIsLoading] = useState(false);
    const [isDataReady, setIsDataReady] = useState(false);
    const loadingTimeInMs = 3.5 * 60 * 1000;

    const { setLocation } = useContext(SelectedLocationContext);
    const { selectedPoints, setSelectedPoints } = useContext(SelectedPointsContext);

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

    const toggleMarkers = (markers) => {
        return fetch(`${backend_url}/toggle-markers`, {
            method: "POST",
            credentials: "include", // Include cookies in the request
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(markers),
        })
            .then((response) => {
                if (response.status === 401) {
                    // Redirect the user to the login page or other unauthorized handling page
                    router.push("/login");
                } else {
                    return response.json();
                }
            })
            .then((data) => {
                if (data) { // to make sure data is not undefined when status is 401
                    console.log(data.message);
                }
            })
            .catch((error) => {
                console.log(error);
            });
    };

    const doneWithChanges = () => {
        setIsLoading(true);
        console.log(selectedPoints);
        // Send request to server to change the selected markers to served
        toggleMarkers(selectedPoints).finally(() => {

            setIsDataReady(true);
            setIsLoading(false);

            setTimeout(() => {
                setIsDataReady(false); // This will be executed 15 seconds after setIsLoading(false)
            }, 5000);
            setSelectedPoints([]);
            router.reload();
        });
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
            <Container component="main" maxWidth="md" className={classes.container}>
                <Typography component="h1" variant="h5" className={classes.headertext}>
                    Your Edits
                </Typography>

                <Typography component="h2" variant="h6" className={classes.headertext}>
                    Single Point Edits
                </Typography>
                <FileTable
                    files={selectedPoints}
                    classes={classes}
                    handleUndoSingleEdit={handleUndoSingleEdit}
                    handleLocateOnMap={handleLocateOnMap}
                />
            </Container>
            <div style={{ marginTop: '20px', marginLeft: '20px' }}>
                <Button
                    variant="contained"
                    color="primary"
                    onClick={doneWithChanges}
                >
                    Submit Changes
                </Button>
            </div>
        </div>

    );
};


const FileTable = ({ files, classes, handleUndoSingleEdit, handleLocateOnMap }) => {

    return (
        <TableContainer component={Paper} style={{ marginBottom: "20px" }}>
            <Table className={classes.table} aria-label="single point table">
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
                                <IconButton
                                    className={classes.deleteButton}
                                    onClick={() => handleUndoSingleEdit(index)}
                                >
                                    <UndoIcon />
                                    <Typography sx={{ marginLeft: "10px" }}>
                                        Undo Point
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

export default MyEdit;