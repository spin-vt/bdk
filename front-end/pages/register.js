import { useState } from 'react';
import { useRouter } from 'next/router';
import { TextField, Button, Typography, Container } from '@material-ui/core';
import { makeStyles } from '@material-ui/core/styles';
import Navbar from '../components/Navbar';
import Swal from 'sweetalert2';
import { backend_url } from '../utils/settings';

const useStyles = makeStyles({
  registerContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    marginTop: '8px',
  },
  registerForm: {
    width: '100%',
    marginTop: '8px',
  },
  registerButtonContainer: {
    marginTop: '16px',
    display: 'flex',
    gap: '16px',
  },
}, {name: 'registerPageStyle'});

const Register = () => {
  const router = useRouter();
  const classes = useStyles();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleRegister = async (e) => {
    e.preventDefault();

    try {
      const response = await fetch(`${backend_url}/api/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
        credentials: 'include', // Add this line
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === "success") {
          router.push('/');
        }
        else {
          if (data.message === "Username already exists.") {
            Swal.fire('Error', 'Username already exists. Please try another one.', 'error');
          }
        }
      } else {
        console.error('Register failed');
      }
    } catch (error) {
      console.error('Register error:', error);
    }
  };

  return (
    <div>
        <Navbar />
    <Container component="main" maxWidth="xs">
      <div className={classes.registerContainer}>
        <Typography component="h1" variant="h5">
          Register
        </Typography>
        <form className={classes.registerForm} onSubmit={handleRegister} noValidate>
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
          <div className={classes.registerButtonContainer}>
          <Button 
            type="submit"
            fullWidth
            variant="contained"
            color="primary">
            Register
          </Button>
          </div>
        </form>
      </div>
    </Container>
    </div>
  );
};

export default Register;