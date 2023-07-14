import styles from '../styles/Home.module.css';
import Navbar from '../components/Navbar';
import dynamic from 'next/dynamic';
import { Drawer } from '@material-ui/core';
import MyFile from '../components/MyFile';
import { useState } from 'react';

const DynamicMap = dynamic(() => import('../components/ToolPage'), { ssr: false });

const HomePage = () => {

  const [myFileOpen, setMyFileOpen] = useState(false);

  const handleDrawerOpen = () => {
    setMyFileOpen(true);
  };

  const handleDrawerClose = () => {
    setMyFileOpen(false);
  };

  return (
    <div>
       <Navbar handleMyFileOpen={handleDrawerOpen} />
      <DynamicMap />
      <Drawer anchor='right' open={myFileOpen} onClose={handleDrawerClose}>
        <MyFile />
      </Drawer>
    </div>
  );
};

export default HomePage;
