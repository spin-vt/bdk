import { useState } from 'react';
import { backend_url } from "../utils/settings";
import Navbar from '../components/Navbar';
import UploadChallenge from '../components/UploadChallenge';
import { Drawer } from '@mui/material';
import MyFile from '../components/MyFile';
import dynamic from 'next/dynamic';
import Swal from 'sweetalert2';


const DynamicMap = dynamic(() => import('../components/Map'), { ssr: false });

function ChallengePage() {
  const [data, setData] = useState(null);
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

  const fetchData = async () => {
    try {
      const response = await fetch(`${backend_url}/api/compute-challenge`);
      const jsonData = await response.json();
      setData(jsonData);
    } catch (error) {
      Swal.fire('Error', 'Oops, something went wrong on our end, try again later', 'error');

    }
  }

  return (
    <div>
      <Navbar handleMyFileOpen={handleDrawerOpen} handleUploadOpen={handleDrawerOpen2} showOnHome={false}/>
      <DynamicMap />
      <button onClick={fetchData}>Fetch Data</button>
      {data && <pre>{JSON.stringify(data, null, 4)}</pre>}
      <CustomDrawer isOpen={myFileOpen} onClose={handleDrawerClose}>
          <MyFile />
      </CustomDrawer>
      <Drawer anchor='right' open={uploadOpen} onClose={handleDrawerClose2}>
          <UploadChallenge/>
      </Drawer>
    </div>
  );
}

const CustomDrawer = ({ isOpen, children, onClose }) => {
  if (!isOpen) return null;  // Don't render the drawer at all if it's not open

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        right: 0,
        width: '750px',
        height: '100%',
        backgroundColor: 'white',
        overflowY: 'scroll',
      }}
    >
      <button
        onClick={onClose}
        style={{
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
          zIndex: '1000'
        }}
      >
        Close
      </button>
      {children}
    </div>
  );
};

export default ChallengePage;
