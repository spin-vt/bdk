import styles from '../styles/Home.module.css';
import Navbar from '../components/Navbar';
import dynamic from 'next/dynamic';

const DynamicMap = dynamic(() => import('../components/Tool'), { ssr: false });

const HomePage = () => {
  return (
    <div>
        <Navbar />
        <DynamicMap />
    </div>
  );
};

export default HomePage;
