import React, { useState, useEffect } from 'react';
import { Button, Container, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Paper, Select, MenuItem, InputLabel, FormControl } from '@mui/material';
import { backend_url } from '../utils/settings';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// Predefined options for dropdowns
const techTypesOptions = {
    "Not Entered": '',
    "(10) Copper Wire": 10,
    "(40) Coaxial Cable / HFC": 40,
    "(50) Optical Carrier / Fiber to the Premises": 50,
    "(60) Geostationary Satellite": 60,
    "(61) Non-geostationary Satellite": 61,
    "(70) Unlicensed Terrestrial Fixed Wireless": 70,
    "(71) Licensed Terrestrial Fixed Wireless": 71,
    "(72) Licensed-by-Rule Terrestrial Fixed Wireless": 72,
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

const typeOptions = {
    "wired": 'wired',
    "wireless": 'wireless',
};


function FileEditTable({ folderId }) {
    const [files, setFiles] = useState([]);

    const fetchnetworkFileInfo = () => {
        const requestOptions = {
            method: 'GET',
            credentials: 'include', // Include cookies in the request
        };
        fetch(`${backend_url}/api/networkfiles/${folderId}`, requestOptions)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    console.log(data);
                    setFiles(data.files_data);
                }
                else {
                    toast.error(data.error);
                }

            })
            .catch(error => console.error("There was an error!", error));

    };


    useEffect(() => {
        fetchnetworkFileInfo();
    }, [folderId]);

    const handleSubmit = (file) => {
       console.log(file);
        const requestOptions = {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(file)
        };
        fetch(`${backend_url}/api/updateNetworkFile/${file.id}`, requestOptions)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    console.log('Update successful');
                    toast.success("Update successful!"); // Display a success toast
                } else {
                    toast.error(data.message);
                }
            })
            .catch(error => {
                console.error("There was an error updating the file!", error);
                toast.error(`Server error`); // Display an error toast
            });
    };


    // Update the files state to reflect the changes locally
    const handleChange = (event, index, field) => {
        const updatedFiles = [...files];
        updatedFiles[index][field] = event.target.value;
        console.log(updatedFiles);
        setFiles(updatedFiles);
    };

    const handleIntegerChange = (event, index, field) => {
        const value = event.target.value;
        // Regular expression to allow only integers
        if (/^\d*$/.test(value)) {
            const updatedFiles = [...files];
            updatedFiles[index][field] = value;
            setFiles(updatedFiles);
        }
    };
    

    return (
        <Container maxWidth="xl">
            <TableContainer component={Paper} sx={{flexGrow: 1}}>
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
                                
                                <EditableCell file={file} field="name" onChange={(event) => handleChange(event, index, 'name')} />
                                <EditableCell file={file} field="type" onChange={(event) => handleChange(event, index, 'type')} />
                                <EditableCell file={file} field="maxDownloadSpeed" onChange={(event) => handleIntegerChange(event, index, 'maxDownloadSpeed')} />
                                <EditableCell file={file} field="maxUploadSpeed" onChange={(event) => handleIntegerChange(event, index, 'maxUploadSpeed')} />
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
                value={file[field] ? file[field] : ''}
                onChange={onChange}
                displayEmpty
            >
                {Object.entries(options).map(([label, value]) => (
                    <MenuItem key={value} value={value}>{label}</MenuItem>
                ))}
            </Select>
        </FormControl>
    );

    const width = field === "name" ? '300px' : '100px'; 
    // Conditionally render Select or TextField based on the field
    switch (field) {
        case 'type':
            return <TableCell>{renderDropdown(typeOptions)}</TableCell>;
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
                        value={file[field] ? file[field] : ''}
                        onChange={onChange}
                        fullWidth
                        style={{ width: width}}
                    />
                </TableCell>
            );
    }
}

export default FileEditTable;
