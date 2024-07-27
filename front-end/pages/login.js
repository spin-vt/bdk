import React, { useState } from "react";
import { useRouter } from "next/router";
import { TextField, Button, Typography, Container } from '@mui/material';
import { styled } from '@mui/material/styles';
import Swal from 'sweetalert2';
import { backend_url } from '../utils/settings';
import styles from '../styles/Login.module.css';
import Navbar from '../components/Navbar';
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

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



const Login = () => {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');


  const validateEmail = (email) => {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).toLowerCase());
  };


  const handleLogin = async (e) => {
    e.preventDefault();

    if (!validateEmail(email)) {
      toast.error("Please enter a valid email address");
    }

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
            toast.error('Incorrect email or password.', 'error');
          }
        }
      }
    } catch (error) {
      toast.error('Error on server side');
    }
  };

  const handleRegisterClick = (event) => {
    event.preventDefault();
    router.push('/register');
  };

  return (
    <div>
      <Navbar />
      <Container component="main">
        <ToastContainer />
        <AuthContainer>
          <LoginContainer>
            <Typography component="h1" variant="h5">
              Sign in with Email and Password
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
            </LoginForm>
          </LoginContainer>
        </AuthContainer>
      </Container>
    </div>
  );
};

export default Login;
