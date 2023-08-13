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

    const handleUndoSingleEdit = (index) => {
        // Create a new array without the item at the given index
        const updatedPoints = [...selectedPoints];
        updatedPoints.splice(index, 1);
        setSelectedPoints(updatedPoints);
    };

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


    return (
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
                                <TableCell>
                                    <IconButton
                                        onClick={() => handleLocateOnMap(file)}
                                    >
                                        <LocationOnIcon />
                                    </IconButton>
                                </TableCell>
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