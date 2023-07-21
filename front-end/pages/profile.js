import { useState } from 'react';
import { useRouter } from 'next/router';
import { TextField, Button, Typography, Container } from '@material-ui/core';
import { makeStyles } from '@material-ui/core/styles';
import Link from 'next/link'
import Navbar from '../components/Navbar';
import Swal from 'sweetalert2';



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