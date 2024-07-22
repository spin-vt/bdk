import React, { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { TextField, Button, Typography, Container } from '@mui/material';
import { styled } from '@mui/material/styles';
import Swal from 'sweetalert2';
import { backend_url } from '../utils/settings';
import { auth, GoogleAuthProvider, EmailAuthProvider } from "../firebase/firebaseConfig";
import "firebaseui/dist/firebaseui.css";
import styles from '../styles/Login.module.css';
import Navbar from '../components/Navbar';

let firebaseui;

const LoginContainer = styled("div")({
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  marginTop: "8px",
});

const LoginForm = styled("form")({
  width: "100%",
  marginTop: "8px",
});

const LoginButtonContainer = styled("div")({
  marginTop: "16px",
  display: "flex",
  gap: "16px",
});

const RegisterButton = styled(Button)({
  marginLeft: "16px",
});

const AuthContainer = styled("div")({
  display: "flex",
  flexDirection: "row",
  justifyContent: "center",
  alignItems: "center",
  width: "100%",
  marginTop: "2%",
});


const Divider = styled("div")({
  height: "400px",
  width: "2px",
  backgroundColor: "#d3d3d3",
  margin: "0 20px",
});

const Login = () => {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();

    try {
      const response = await fetch(`${backend_url}/api/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
        credentials: 'include',
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === 'success') {
          router.push('/');
        } else {
          if (data.message === 'Invalid credentials') {
            Swal.fire('Error', 'Incorrect email or password.', 'error');
          }
        }
      } else {
        console.log("Login failed")
        Swal.fire('Error', 'Incorrect credentials', 'error');
      }
    } catch (error) {
      console.log("Login error ", error)
      Swal.fire('Error', 'Incorrect credentials', 'error');
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
        <AuthContainer>
          <LoginContainer>
            <Typography component="h1" variant="h5">
              Sign in with Username and Password
            </Typography>
            <LoginForm onSubmit={handleLogin} noValidate>
              <TextField
                variant="outlined"
                margin="normal"
                required
                fullWidth
                id="email"
                label="Email"
                name="email"
                autoComplete="email"
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                key="email-input"
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
              <LoginButtonContainer>
                <Button
                  type="submit"
                  fullWidth
                  variant="contained"
                  color="primary"
                >
                  Sign In
                </Button>
                <RegisterButton
                  fullWidth
                  variant="contained"
                  color="secondary"
                  onClick={handleRegisterClick}>
                  Register
                </RegisterButton>
              </LoginButtonContainer>
              <Button
                fullWidth
                variant="text"
                color="primary"
                onClick={() => router.push('/resetPassword')}
                style={{ marginTop: '1rem' }}
              >
                Forgot Password?
              </Button>
            </LoginForm>
          </LoginContainer>

          <Divider></Divider>
          <div id="firebaseui-auth-container"></div>

          <div className={styles.container}>
            <div id="firebaseui-auth-container"></div>
          </div>
        </AuthContainer>
      </Container>
    </div>
  );
};

export default Login;