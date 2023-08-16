import Navbar from '../components/Navbar';
import { Typography, Container } from '@mui/material';



const Profile = () => {
  return (
    <div>
      <Navbar />
      <Container component="main" maxWidth="xs">
        <div>
          <Typography component="h1" variant="h5">
            Profile
          </Typography>
        </div>
      </Container>
    </div>
  );
};

export default Profile;