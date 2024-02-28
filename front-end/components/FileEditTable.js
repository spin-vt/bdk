import React, { useState, useEffect } from 'react';
import { Button, Container, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Paper, Select, MenuItem, InputLabel, FormControl } from '@mui/material';
import { backend_url } from '../utils/settings';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// Predefined options for dropdowns
const techTypesOptions = {
    "Not Entered": '',
    "Copper Wire": 10,
    "Coaxial Cable / HFC": 40,
    "Optical Carrier / Fiber to the Premises": 50,
    "Geostationary Satellite": 60,
    "Non-geostationary Satellite": 61,
    "Unlicensed Terrestrial Fixed Wireless": 70,
    "Licensed Terrestrial Fixed Wireless": 71,
    "Licensed-by-Rule Terrestrial Fixed Wireless": 72,
    "Other": 0,
};
const latencyOptions = {
    "Not Entered": '',
    "<= 100 ms": 1,
    "> 100 ms": 0,
};
const categoryOptions = {
    "Not Entered": '',
    Business: "B",
    Residential: "R",
    Both: "X",
};


function FileEditTable({ folderId }) {
    const [files, setFiles] = useState([]);
    const [originalNetworkInfo, setOriginalNetworkInfo] = useState([]);

    const fetchnetworkFileInfo = () => {
        const requestOptions = {
            method: 'GET',
            credentials: 'include', // Include cookies in the request
        };
        fetch(`${backend_url}/api/networkfiles/${folderId}`, requestOptions)
            .then(response => response.json())
            .then(data => {
                const dataWithDefaultNetworkInfo = data.map(file => ({
                    ...file,
                    // Ensure network_info is an object
                    network_info: file.network_info || {}
                }));
                setFiles(dataWithDefaultNetworkInfo);
                setOriginalNetworkInfo(JSON.parse(JSON.stringify(dataWithDefaultNetworkInfo)));

            })
            .catch(error => console.error("There was an error!", error));

    };


    useEffect(() => {
        fetchnetworkFileInfo();
    }, [folderId]);

    const handleSubmit = (file) => {
        const originalFile = originalNetworkInfo.find(origFile => origFile.id === file.id);
        const hasChanges = Object.keys(file.network_info).some(key =>
            (file.network_info[key] || '') !== (originalFile.network_info[key] || '')
        );

        if (!hasChanges) {
            console.log("No changes detected, no update required.");
            toast.info("No changes detected."); // Display an info toast
            return; // Exit if no changes were detected
        }

        const requestOptions = {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(file)
        };
        fetch(`${backend_url}/api/updateNetworkFile/${file.id}`, requestOptions)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Update successful');
                    // Update originalNetworkInfo to reflect the changes
                    const updatedOriginalNetworkInfo = originalNetworkInfo.map(origFile =>
                        origFile.id === file.id ? { ...origFile, network_info: { ...file.network_info } } : origFile
                    );
                    setOriginalNetworkInfo(updatedOriginalNetworkInfo);
                    toast.success("Update successful!"); // Display a success toast
                } else {
                    throw new Error(data.message || "An error occurred during the update.");
                }
            })
            .catch(error => {
                console.error("There was an error updating the file!", error);
                toast.error(`Error updating file: ${error.message}`); // Display an error toast
            });
    };


    // Update the files state to reflect the changes locally
    const handleChange = (event, index, field) => {
        const updatedFiles = [...files];
        updatedFiles[index].network_info[field] = event.target.value;
        setFiles(updatedFiles);
    };

    return (
        <Container>
            <TableContainer component={Paper}>
                <Table sx={{ minWidth: 650 }} aria-label="editable table">
                    <TableHead>
                        <TableRow>
                            <TableCell>Name</TableCell>
                            <TableCell>Type</TableCell>
                            <TableCell>Max Download Speed</TableCell>
                            <TableCell>Max Upload Speed</TableCell>
                            <TableCell>Tech Type</TableCell>
                            <TableCell>Latency</TableCell>
                            <TableCell>Category</TableCell>
                            <TableCell>Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {files.map((file, index) => (
                            <TableRow
                                key={file.id}
                                sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                            >
                                <TableCell component="th" scope="row">{file.name}</TableCell>
                                <TableCell>{file.type}</TableCell>
                                <EditableCell file={file} field="maxDownloadSpeed" onChange={(event) => handleChange(event, index, 'maxDownloadSpeed')} />
                                <EditableCell file={file} field="maxUploadSpeed" onChange={(event) => handleChange(event, index, 'maxUploadSpeed')} />
                                <EditableCell file={file} field="techType" onChange={(event) => handleChange(event, index, 'techType')} />
                                <EditableCell file={file} field="latency" onChange={(event) => handleChange(event, index, 'latency')} />
                                <EditableCell file={file} field="category" onChange={(event) => handleChange(event, index, 'category')} />
                                <TableCell>
                                    <Button variant="contained" onClick={() => handleSubmit(file)}>Save Changes</Button>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
            <ToastContainer position="top-right" autoClose={5000} hideProgressBar={false} newestOnTop={false} closeOnClick rtl={false} pauseOnFocusLoss draggable pauseOnHover />
        </Container>
    );
}

// EditableCell component to render a TextField if network_info is present
function EditableCell({ file, field, onChange }) {
    const renderDropdown = (options) => (
        <FormControl fullWidth size="small">
            <Select
                value={file.network_info && file.network_info[field] !== undefined ? file.network_info[field] : ''}
                onChange={onChange}
                displayEmpty
            >
                {Object.entries(options).map(([label, value]) => (
                    <MenuItem key={value} value={value}>{label}</MenuItem>
                ))}
            </Select>
        </FormControl>
    );

    // Conditionally render Select or TextField based on the field
    switch (field) {
        case 'techType':
            return <TableCell>{renderDropdown(techTypesOptions)}</TableCell>;
        case 'latency':
            return <TableCell>{renderDropdown(latencyOptions)}</TableCell>;
        case 'category':
            return <TableCell>{renderDropdown(categoryOptions)}</TableCell>;
        default:
            return (
                <TableCell>
                    <TextField
                        variant="outlined"
                        value={file.network_info ? file.network_info[field] : ''}
                        onChange={onChange}
                        size="small"
                        fullWidth
                    />
                </TableCell>
            );
    }
}

export default FileEditTable;
