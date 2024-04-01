import styles from "../styles/Home.module.css";
import Navbar from "../components/Navbar";
import dynamic from "next/dynamic";
import { Drawer } from "@mui/material";
import MyFile from "../components/MyFile";
import Upload from "../components/Upload";
import { useContext, useState } from "react";
import LayerVisibilityProvider from "../contexts/LayerVisibilityProvider";
import SelectedLocationProvider from "../contexts/SelectedLocationProvider";
import EditMapContext from "../contexts/EditMapContext";
import MyEdit from "../components/MyEdit";
import SelectedPointsProvider from "../contexts/SelectedPointsProvider";
import SelectedPolygonProvider from "../contexts/SelectedPolygonProvider";
import {DeadlineProvider} from '../contexts/DeadlineContext';
import { styled } from '@mui/material/styles';
import { Typography } from "@mui/material";


const DynamicMap = dynamic(() => import("../components/Map"), { ssr: false });
const Editmap = dynamic(() => import("../components/Editmap"), { ssr: false });

const StyledTypography = styled(Typography)({
  marginTop: "20px",
  marginBottom: "20px",
});


const HomePage = () => {
  const [myFileOpen, setMyFileOpen] = useState(false);
  const [uploadOpen, setOpen] = useState(false);
  const { isEditingMap } = useContext(EditMapContext);

  const handleDrawerOpen = () => {
    setMyFileOpen(true);
  };

  const handleDrawerClose = () => {
    setMyFileOpen(false);
  };

  const handleDrawerOpen2 = () => {
    setOpen(true);
  };

  const handleDrawerClose2 = () => {
    setOpen(false);
  };

  return (
    <div>
      <DeadlineProvider>
      <LayerVisibilityProvider>
        <SelectedLocationProvider>
          <SelectedPointsProvider>
            <SelectedPolygonProvider>
            <Navbar
              sx={{ height: "10vh" }}
              handleMyFileOpen={handleDrawerOpen}
              handleUploadOpen={handleDrawerOpen2}
              showOnHome={true}
            />
            {isEditingMap ? <Editmap /> : <DynamicMap />} 
            {/* This is where I will add filing logic */}
            <CustomDrawer isOpen={myFileOpen} onClose={handleDrawerClose}>
              {isEditingMap ? <MyEdit /> : <MyFile />}
            </CustomDrawer>

            <Drawer
              anchor="right"
              open={uploadOpen}
              onClose={handleDrawerClose2}
            >
              <StyledTypography component="h1" variant="h5" marginLeft={"1vw"}>
                Upload Network Files Below:
              </StyledTypography>
              <Upload generateChallenge={false}/> {/*Set it to always false for now to upload files for filling*/}
            </Drawer>
            </SelectedPolygonProvider>
          </SelectedPointsProvider>
        </SelectedLocationProvider>
      </LayerVisibilityProvider>
      </DeadlineProvider>
    </div>
  );
};

const CustomDrawer = ({ isOpen, children, onClose }) => {
  if (!isOpen) return null; // Don't render the drawer at all if it's not open

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        right: 0,
        width: "750px",
        height: "100%",
        backgroundColor: "white",
        overflowY: "scroll",
      }}
    >
      <button
        onClick={onClose}
        style={{
          position: "absolute",
          top: "10px",
          right: "10px",
          padding: "8px 16px",
          background: "red",
          color: "white",
          border: "none",
          borderRadius: "4px",
          cursor: "pointer",
          fontSize: "16px",
          zIndex: "1000",
          position: 'absolute',
          top: '10px',
          right: '10px',
          padding: '8px 16px',
          background: 'red',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          fontSize: '16px',
          zIndex: '2000'
        }}
      >
        Close
      </button>
      {children}
    </div>
  );
};

export default HomePage;
