import Navbar from "../components/Navbar";
import { Drawer } from "@mui/material";
import { useContext, useState } from "react";
import { styled } from '@mui/material/styles';
import { Typography } from "@mui/material";
import dynamic from "next/dynamic";
import {useFolder} from "../contexts/FolderContext.js";


const FileEditTable = dynamic(() => import("../components/FileEditTable"), { ssr: false });

const StyledTypography = styled(Typography)({
    marginTop: "20px",
    marginBottom: "20px",
});


const editfileinfo = () => {
    const {folderID, setFolderID} = useFolder();

    return (
        <div>
            <Navbar />
            <FileEditTable folderId={folderID} sx={{marginTop:'30px'}}/>
        </div>
    );
};


export default editfileinfo;
