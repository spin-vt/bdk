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
import SelectedPolygonProvider from "../contexts/SelectedPolygonProvider";
import SelectedPolygonAreaProvider from "../contexts/SelectedPolygonAreaProvider";
import EditLayerVisibilityProvider from "../contexts/EditLayerVisibilityProvider";
import { styled } from '@mui/material/styles';
import { Typography, Container, Box } from "@mui/material";
import Edit from "@mui/icons-material/Edit";

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

            <LayerVisibilityProvider>
              <EditLayerVisibilityProvider>
                <SelectedLocationProvider>
                  <SelectedPolygonProvider>
                    <SelectedPolygonAreaProvider>
                      <Navbar
                        sx={{ height: "10%" }}
                        handleMyFilingOpen={handleDrawerOpen}
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
                        <Upload />
                      </Drawer>
                    </SelectedPolygonAreaProvider>
                  </SelectedPolygonProvider>
                </SelectedLocationProvider>
              </EditLayerVisibilityProvider>
            </LayerVisibilityProvider>

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
        backgroundColor: "#f9f9f9", // Changed to a lighter grey shade
        overflowY: "auto", // Use auto to only show scrollbar when necessary
        boxShadow: "0px 0px 10px rgba(0,0,0,0.5)", // Adds shadow for depth
        transition: "right 0.3s ease", // Smooth transition for sliding effect
      }}
    >
      <button
        onClick={onClose}
        style={{
          position: "absolute",
          top: "10px",
          right: "10px",
          padding: "8px 16px",
          background: "#686df2", // A more subdued shade of red
          color: "white",
          border: "none",
          borderRadius: "8px", // More rounded corners
          cursor: "pointer",
          fontSize: "16px",
          zIndex: "2000",
          boxShadow: "0px 2px 4px rgba(0,0,0,0.3)", // Subtle shadow for the button
          transition: "background 0.2s", // Transition effect for hover
        }}
      >
        Close
      </button>
      {children}
    </div>
  );
};


export default HomePage;
