import Navbar from "../components/Navbar";
import { Drawer } from "@mui/material";
import { useContext, useState } from "react";
import { styled } from '@mui/material/styles';
import { Typography } from "@mui/material";
import dynamic from "next/dynamic";

const FileEditTable = dynamic(() => import("../components/FileEditTable"), { ssr: false });

const StyledTypography = styled(Typography)({
    marginTop: "20px",
    marginBottom: "20px",
});


const editfileinfo = () => {

    return (
        <div>
            <Navbar />
            {/* Set folder id to 1 for now, adjust when user can choose multiple filings */}
            <FileEditTable folderId={1} sx={{marginTop:'30px'}}/>
        </div>
    );
};


export default editfileinfo;
