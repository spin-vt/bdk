import { useState } from 'react';
import { useRouter } from 'next/router';
import { TextField, Button, Typography, Container } from '@material-ui/core';
import { makeStyles } from '@material-ui/core/styles';
import Link from 'next/link'
import Navbar from '../components/Navbar';
import Swal from 'sweetalert2';

const useStyles = makeStyles((theme) => ({
  loginContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    marginTop: theme.spacing(1),
  },
  loginForm: {
    width: '100%',
    marginTop: theme.spacing(1),
  },
  loginButtonContainer: {
    marginTop: theme.spacing(2),
    display: 'flex',
    gap: theme.spacing(2),
  },
  registerButton: {
    marginLeft: theme.spacing(2),
  },
}));

const Login = () => {
  const router = useRouter();
  const classes = useStyles();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();

    try {
      const response = await fetch('http://backend:5000/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
        credentials: 'include', // Add this line
      });

      if (response.ok) {
        const data = await response.json(); // Extract JSON from the response
        if (data.status === 'success') {
          router.push('/');
        }
        else {
          if (data.message === 'Invalid credentials') {
            Swal.fire('Error', 'Incorrect username or password.', 'error');
          }
        }
      } else {
        console.error('Login failed');
      }
    } catch (error) {
      console.error('Login error:', error);
    }
  };

  const handleRegisterClick = (event) => {
    event.preventDefault(); // Prevent the default behavior
    // Navigate to the login page
    router.push('/register');
  };

  return (
    <div>
      <Navbar />
    <Container component="main" maxWidth="xs">
      <div className={classes.loginContainer}>
        <Typography component="h1" variant="h5">
          Sign in
        </Typography>
        <form className={classes.loginForm} onSubmit={handleLogin} noValidate>
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
          <div className={classes.loginButtonContainer}>
          <Button
            type="submit"
            fullWidth
            variant="contained"
            color="primary"
          >
            Sign In
          </Button>
          <Button 
            fullWidth
            variant="contained"
            color="secondary"
            className={classes.registerButton}
            onClick={handleRegisterClick}>
              Register
          </Button>
          </div>
        </form>
      </div>
    </Container>
    </div>
  );
};

export default Login;