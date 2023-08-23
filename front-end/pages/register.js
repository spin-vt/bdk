import { useState } from 'react';
import { useRouter } from 'next/router';
import { TextField, Button, Typography, Container } from '@mui/material';
import Navbar from '../components/Navbar';
import Swal from 'sweetalert2';
import { backend_url } from '../utils/settings';
import { styled } from '@mui/system';

const RegisterContainer = styled('div')({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  marginTop: '8px',
});

const RegisterForm = styled('form')({
  width: '100%',
  marginTop: '8px',
});

const RegisterButtonContainer = styled('div')({
  marginTop: '16px',
  display: 'flex',
  gap: '16px',
});


const Register = () => {
  const router = useRouter();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [providerId, setProviderId] = useState('');
  const [brandName, setBrandName] = useState('');  

  const handleRegister = async (e) => {
    e.preventDefault();

    try {
      const response = await fetch(`${backend_url}/api/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password, providerId, brandName }),  
        credentials: 'include',
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === "success") {
          router.push('/');
        }
      } else if (response.status === 400) {
        const data = await response.json();
        if (data.message === "Username already exists") {
          Swal.fire('Error', 'Username already exists. Please try another one.', 'error');
        }
      }
    } catch (error) {
      console.error('Register error:', error);
    }
  };

  return (
    <div>
      <Navbar />
      <Container component="main" maxWidth="xs">
        <RegisterContainer>
          <Typography component="h1" variant="h5">
            Register
          </Typography>
          <RegisterForm onSubmit={handleRegister} noValidate>
            <TextField
              variant="outlined"
              margin="normal"
              required
              fullWidth
              id="username"
              label="Username"
              name="username"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              key="username-input"
            />
            <TextField
              variant="outlined"
              margin="normal"
              required
              fullWidth
              name="password"
              label="Password"
              type="password"
              id="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              key="password-input"
            />
            <TextField
              variant="outlined"
              margin="normal"
              required
              fullWidth
              id="providerId"
              label="Provider ID"
              name="providerId"
              value={providerId}
              onChange={(e) => setProviderId(e.target.value)}
              key="providerId-input"
            />
            <TextField
              variant="outlined"
              margin="normal"
              required
              fullWidth
              id="brandName"
              label="Brand Name"
              name="brandName"
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              key="brandName-input"
            />
            <RegisterButtonContainer>
              <Button
                type="submit"
                fullWidth
                variant="contained"
                color="primary">
                Register
              </Button>
            </RegisterButtonContainer>
          </RegisterForm>
        </RegisterContainer>
      </Container>
    </div>
  );
};

export default Register;