import styles from '../styles/Home.module.css';
import Navbar from '../components/Navbar';
import dynamic from 'next/dynamic';
import SelectedLocationProvider from '../components/SelectLocationProvider';

const DynamicMap = dynamic(() => import('../components/ToolPage'), { ssr: false });

const HomePage = () => {
  return (
    <div>
      <SelectedLocationProvider>
        <Navbar />
        <DynamicMap />
      </SelectedLocationProvider>

    </div>
  );
};

export default HomePage;
