import * as React from "react";
import { DataGrid } from "@mui/x-data-grid";
import { Button, FormControl, InputLabel, MenuItem, Select, Box, Grid, styled } from '@mui/material';
import Swal from "sweetalert2";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { useFolder } from '../contexts/FolderContext';
import { useRouter } from "next/router";
import { format } from "date-fns";
import { backend_url } from "../utils/settings";
import FetchTaskInfoContext from "../contexts/FetchTaskInfoContext";
import ReloadMapContext from "../contexts/ReloadMapContext";



const tech_types = {
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

const latency_type = {
    "<= 100 ms": 1,
    "> 100 ms": 0,
};

const bus_codes = {
    Business: "B",
    Residential: "R",
    Both: "X",
};

const StyledInput = styled('input')({
    display: 'none',
});



export default function Upload() {
    const router = useRouter();
    const [files, setFiles] = React.useState([]);
    const [folders, setFolders] = React.useState([]);


    const { folderID, setFolderID } = useFolder();

    const [importFolderID, setImportFolderID] = React.useState(-1);

    const months = Array.from({ length: 12 }, (_, i) => i + 1); // Months 1-12
    const currentYear = new Date().getFullYear();
    const years = Array.from({ length: 10 }, (_, i) => currentYear - 5 + i);

    const [newDeadline, setNewDeadline] = React.useState({ month: '', year: '' });

    const [errorRows, setErrorRows] = React.useState(new Set());

    const [fileIdCounter, setFileIdCounter] = React.useState(0);

    const [previousFiles, setPreviousFiles] = React.useState([]);

    const allowedExtensions = ["kml", "geojson", "csv"];
    const { setShouldFetchTaskInfo } = React.useContext(FetchTaskInfoContext);

    const { setShouldReloadMap } = React.useContext(ReloadMapContext);

    const fetchFiles = async (folderId, importFolderId) => {
        let folderToFetch = folderId;
        if (folderToFetch === -1) {
            if (importFolderId != -1) {
                folderToFetch = importFolderId;
            }
            else {
                return;
            }
        }

        const response = await fetch(`${backend_url}/api/files?folder_ID=${folderToFetch}`, {
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
        if (data.status === 'error') {
            toast.error(data.message);
            return;
        }


        setPreviousFiles(data.map(file => ({ name: file.name })));
    };

    React.useEffect(() => {

        fetchFiles(folderID, importFolderID);
    }, [folderID, importFolderID]);

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



    const handleDeadlineSelect = (newFolderID) => {
        if (newFolderID === folderID) {
            return;
        }
        if (newFolderID === -1) {
            // Reset deadline selection
            setNewDeadline({ month: '', year: '' });
        }
        else {
            const selectedFolder = folders.find(folder => folder.folder_id === newFolderID);
            if (selectedFolder) {
                // Parse the deadline date of the selected folder
                const date = new Date(selectedFolder.deadline);
                const month = date.getMonth() + 1;  // getMonth() is zero-indexed, so add 1
                const year = date.getFullYear();
                // Set newDeadline to reflect the selected folder's deadline
                setNewDeadline({ month: month.toString(), year: year.toString() });
            }
        }
        setFolderID(newFolderID);
        setShouldReloadMap(true);
    };

    const handleImportChange = (event) => {
        const selectedFolderID = event.target.value;
        setImportFolderID(selectedFolderID);

    };

    const handleNewDeadlineChange = ({ month, year }) => {

        setNewDeadline({ month, year });

    };


    const handleDelete = (id) => {
        setFiles(files.filter(file => file.id !== id));
    };

    const handleFileChange = async (event) => {
        const fileArray = Array.from(event.target.files);
        let currentId = fileIdCounter;
        const newFiles = [];

        for (const file of fileArray) {
            // Check if the file is already in the selected files
            const existingFile = files.find(f => f.name === file.name);
            if (existingFile) {
                toast.error(`File '${file.name}' is already selected.`);
                continue;  // Skip to the next file
            }

            // Check if the file exists on the server
            const fileExistsOnServer = previousFiles.some(f => f.name === file.name);
            if (fileExistsOnServer) {
                toast.error(`The file "${file.name}" already exists on the server. If this is a different document, please rename it and upload again.`);
                continue;  // Skip to the next file
            }

            newFiles.push({
                id: currentId++,
                name: file.name,
                downloadSpeed: '',
                uploadSpeed: '',
                techType: '',
                networkType: '',
                latency: '',
                categoryCode: '',
                file,
            });
        }

        setFileIdCounter(currentId); // Update fileIdCounter to the new value after all files are processed
        setFiles(prevFiles => [...prevFiles, ...newFiles]); // Properly append new files to the existing list
    };

    const handleRowUpdate = (newRow) => {
        setFiles(prevFiles => prevFiles.map(file => {
            if (file.id === newRow.id) {
                return newRow;  // return the modified newRow directly
            }
            return file;
        }));
        return newRow;  // Important: Return the modified newRow to the DataGrid
    };


    React.useEffect(() => {
        fetchFolders();
    }, []);


    const columns = [
        { field: "name", headerName: "File Name", width: 250, editable: true },
        { field: "downloadSpeed", headerName: "Download Speed (Mbps)", type: 'number', editable: true },
        { field: "uploadSpeed", headerName: "Upload Speed (Mbps)", type: 'number', editable: true },
        { field: "techType", headerName: "Technology Type", width: 250, type: 'singleSelect', valueOptions: Object.keys(tech_types), editable: true },
        { field: "networkType", headerName: "Network Type", type: 'singleSelect', valueOptions: ["wired", "wireless"], editable: true },
        { field: "latency", headerName: "Latency", type: 'singleSelect', valueOptions: Object.keys(latency_type), editable: true },
        { field: "categoryCode", headerName: "Category", type: 'singleSelect', valueOptions: Object.keys(bus_codes), editable: true },
        {
            field: "delete",
            headerName: "Delete",
            sortable: false,
            width: 100,
            renderCell: (params) => (
                <Button
                    color="error"
                    onClick={() => handleDelete(params.id)}
                >
                    Delete
                </Button>
            )
        }
    ];

    const getRowClassName = (params) => {
        return errorRows.has(params.id) ? 'error-row' : 'normal-row';
    };

    const processFiles = () => {

        if (files.length === 0) {
            toast.error("Please upload your file");
            return;
        }

        if (folderID === -1 && !files.some(file => file.file.name.endsWith('.csv'))) {
            toast.error("Please upload your fabric");
            return; // Stop the function if the condition is met
        }

        let hasErrors = false;
        let newErrorRows = new Set();

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            if (file.file.name.endsWith('.csv')) {
                continue; // Skip the rest of the current iteration and continue with the next file
            }
            console.log(file);
            if (!file.downloadSpeed || !file.uploadSpeed || !file.techType || !file.networkType || !file.latency || !file.categoryCode) {
                hasErrors = true;
                newErrorRows.add(file.id);
            }
        }


        setErrorRows(newErrorRows);


        if (hasErrors) {
            toast.error("Please fill all required fields before submitting.");
            return;
        }


        const formData = new FormData();
        formData.append("deadline", `${newDeadline.year}-${newDeadline.month}-03`);
        formData.append("importFolder", importFolderID);


        files.forEach((fileDetails) => {
            const fileExtension = fileDetails.file.name
                .split(".")
                .pop()
                .toLowerCase();

            if (!allowedExtensions.includes(fileExtension)) {
                toast.error("Invalid File Format. Please upload a KML, GeoJSON, or CSV file.");
                return;
            }

            const processedFileDetails = {
                ...fileDetails,
                techType: tech_types[fileDetails.techType],
                latency: latency_type[fileDetails.latency],
                categoryCode: bus_codes[fileDetails.categoryCode],
            };

            console.log(processedFileDetails);
    
            formData.append("fileData", JSON.stringify(processedFileDetails));
            formData.append("file", fileDetails.file);
        });



        fetch(`${backend_url}/api/submit-data/${folderID}`, {
            method: "POST",
            body: formData,
            credentials: "include",
        })
            .then((response) => {
                if (response.status === 401) {
                    Swal.fire({
                        icon: "error",
                        title: "Oops...",
                        text: "Session expired, please log in again!",
                    });
                    // Redirect to login page
                    router.push("/login");
                    return;
                } else {
                    return response.json();
                } 
            })
            .then((data) => {
                if (data.status === 'success') {
                    toast.success("Your file is uploaded to the server for processing");
                    setFiles([]);
                    setShouldFetchTaskInfo(true);
                }
                else {
                    if (data.message === "Create or join an organization to start working on a filing"){
                        Swal.fire({
                            icon: "error",
                            title: "Oops...",
                            text: data.message,
                        });
                        router.push("/profile");
                    }
                    else {
                        toast.error(data.message);
                    }
                }
            })
            .catch((error) => {
                Swal.fire({
                    icon: "error",
                    title: "Oops...",
                    text: "There is an error on our end, please try again later",
                });
                console.error("Error:", error);

            });
    };

    return (
        <React.Fragment>
           
            <ToastContainer />
            <div>
                <FormControl style={{ width: '300px', marginBottom: '20px' }}>
                    <InputLabel id="filing-select-label">You are working on filing for deadline:</InputLabel>
                    <Select
                        labelId="filing-select-label"
                        id="filing-select"
                        value={folderID}
                        label="You are working on Filing for Deadline:"
                        onChange={(e) => handleDeadlineSelect(e.target.value)}
                    >
                        <MenuItem value={-1}><em>Create New Filing for Deadline:</em></MenuItem>
                        {folders.map((folder) => (
                            <MenuItem key={folder.deadline} value={folder.folder_id}>
                                {format(new Date(folder.deadline), 'MMMM yyyy')}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>
                {folderID === -1 && (
                    <>
                        <FormControl style={{ width: '120px' }}>
                            <InputLabel id="month-select-label">Month</InputLabel>
                            <Select
                                labelId="month-select-label"
                                id="month-select"
                                value={newDeadline.month}
                                label="Month"
                                onChange={e => handleNewDeadlineChange({ ...newDeadline, month: e.target.value })}
                            >
                                {months.map(month => (
                                    <MenuItem key={month} value={month}>{month}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <FormControl style={{ width: '120px', marginRight: '20px' }}>
                            <InputLabel id="year-select-label">Year</InputLabel>
                            <Select
                                labelId="year-select-label"
                                id="year-select"
                                value={newDeadline.year}
                                label="Year"
                                onChange={e => handleNewDeadlineChange({ ...newDeadline, year: e.target.value })}
                            >
                                {years.map(year => (
                                    <MenuItem key={year} value={year}>{year}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <FormControl style={{ width: '300px', border: '1px solid #78fff1' }}>
                            <InputLabel id="import-select-label">Import Data from Previous Filing</InputLabel>
                            <Select
                                labelId="import-select-label"
                                id="import-select"
                                value={importFolderID}
                                onChange={handleImportChange}
                            >
                                <MenuItem value={-1}>
                                    <em>Don't Import</em>
                                </MenuItem>
                                {folders.map(folder => (
                                    <MenuItem key={folder.folder_id} value={folder.folder_id}>
                                        {format(new Date(folder.deadline), 'MMMM yyyy')}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </>
                )}
            </div>
            <Box sx={{ width: '100%', minHeight: 400 }}>

                <DataGrid
                    rows={files}
                    columns={columns}
                    editMode="row"
                    pageSize={5}
                    getRowClassName={({ id }) => getRowClassName({ id })}
                    processRowUpdate={handleRowUpdate}
                    sx={{
                        '.MuiDataGrid-row': (theme) => ({
                            '&.error-row': {
                                backgroundColor: '#ffcccc', // Light red background for error rows
                                color: '#cc0000', // Darker red text for error rows
                            },
                            '&.normal-row': {
                                backgroundColor: '', // Light red background for error rows
                                color: '', // Darker red text for error rows
                            }
                        })
                    }}
                />
            </Box>
            <Button color="primary" onClick={processFiles}>Submit Files</Button>

            <Button component="label" color="secondary">
                Add File
                <StyledInput
                    accept="*/*"
                    type="file"
                    multiple
                    onChange={handleFileChange}
                    hidden
                />
            </Button>
        </React.Fragment>
    );
}
