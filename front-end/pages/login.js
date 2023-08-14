import React, { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { TextField, Button, Typography, Container } from '@material-ui/core';
import { makeStyles } from '@material-ui/core/styles';
import Swal from 'sweetalert2';
import { backend_url } from '../utils/settings';
import { auth, GoogleAuthProvider, EmailAuthProvider } from "../firebase/firebaseConfig";
import "firebaseui/dist/firebaseui.css";
import styles from '../styles/Login.module.css';
import Navbar from '../components/Navbar';

let firebaseui;

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
  authContainer: {
    display: 'flex',
    flexDirection: 'row',
    justifyContent: 'center', // changed to center
    alignItems: 'center',
    width: '100%',
    marginTop: '-7%', // adjust the value as required to move higher
  },
  root: {
    height: '100vh',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f7f7f7',
  },
  mainContainer: {
    boxShadow: '0px 4px 20px rgba(0, 0, 0, 0.1)',
    borderRadius: '8px',
    overflow: 'hidden',
    backgroundColor: '#fff',
  },
  divider: {
    height: '400px',
    width: '2px',
    backgroundColor: '#d3d3d3',
    margin: '0 20px',
  }
}));

const Login = () => {
  const router = useRouter();
  const classes = useStyles();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();

    try {
      const response = await fetch(`${backend_url}/api/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
        credentials: 'include',
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === 'success') {
          router.push('/');
        } else {
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
    event.preventDefault();
    router.push('/register');
  };

  useEffect(() => {
    if (typeof window !== "undefined") {
      firebaseui = require('firebaseui');
      const uiConfig = {
        signInSuccessUrl: "/",
        signInOptions: [
          GoogleAuthProvider.PROVIDER_ID,
          EmailAuthProvider.PROVIDER_ID,
        ],
        callbacks: {
          signInSuccessWithAuthResult: async (authResult) => {
            if (typeof window !== "undefined") {
              
              // Extracting user information
              const { user } = authResult;
              const username = user.email; // Using email as the username
              const password = user.uid;   // Using uid as a placeholder password
        
              // Send this information to your backend
              try {
                const response = await fetch(`${backend_url}/api/register`, {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({ username, password }),  // send them as required by your backend
                  credentials: 'include',
                });
        
                if (response.ok) {
                  const data = await response.json();
                  if (data.status !== 'success') {
                    Swal.fire('Error', data.message || 'Unknown error occurred during registration.', 'error');
                  }
                } else {
                  Swal.fire('Error', 'Failed to register with Firebase.', 'error');
                }
        
              } catch (error) {
                Swal.fire('Error', 'Failed to register with Firebase.', 'error');
                console.error('Firebase registration error:', error);
              }
              
              window.location.href = "/";
            }
            return false;
          },
        },
      };

      let ui = firebaseui.auth.AuthUI.getInstance();
      if (!ui) {
        ui = new firebaseui.auth.AuthUI(auth);
      }
      ui.start("#firebaseui-auth-container", uiConfig);

      return () => {
        ui.delete();
      };
    }
  }, []);

  return (
    <div>
      <Navbar />
      <Container component="main">
        <div className={classes.authContainer}>
          <div className={classes.loginContainer}>
            <Typography component="h1" variant="h5">
              Sign in with Username and Password
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

          <div className={classes.divider}></div>
          <Typography component="h2" variant="h6" style={{textAlign: 'center', marginBottom: '1em'}}>
          Or with these providers
        </Typography>
          <div id="firebaseui-auth-container"></div>

          <div className={styles.container}>
            <div id="firebaseui-auth-container"></div>
          </div>
        </div>
      </Container>
    </div>
  );
};

export default Login;