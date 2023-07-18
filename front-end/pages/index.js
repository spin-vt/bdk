import styles from '../styles/Home.module.css';
import Navbar from '../components/Navbar';
import dynamic from 'next/dynamic';
import { Drawer } from '@material-ui/core';
import MyFile from '../components/MyFile';
import Upload from '../components/Upload';
import { useState } from 'react';
import LayerVisibilityProvider from '../contexts/LayerVisibilityProvider';
import SelectedLocationProvider from '../contexts/SelectLocationProvider';

const DynamicMap = dynamic(() => import('../components/ToolPage'), { ssr: false });

const HomePage = () => {

  const [myFileOpen, setMyFileOpen] = useState(false);
  const [uploadOpen, setOpen] = useState(false);

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
        <SelectedLocationProvider>
       <Navbar handleMyFileOpen={handleDrawerOpen} handleUploadOpen={handleDrawerOpen2}/>
      <DynamicMap />
      <Drawer anchor='right' open={myFileOpen} onClose={handleDrawerClose}>
        <MyFile />
      </Drawer>
      <Drawer anchor='right' open={uploadOpen} onClose={handleDrawerClose2}>
        <Upload />
      </Drawer>
      </SelectedLocationProvider>
      </LayerVisibilityProvider>
    </div>
  );
};

export default HomePage;
