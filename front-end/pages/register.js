import { useState } from "react";
import { useRouter } from "next/router";
import { TextField, Button, Typography, Container } from "@mui/material";
import Navbar from "../components/Navbar";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { backend_url } from "../utils/settings";
import { styled } from "@mui/system";

const RegisterContainer = styled("div")({
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  marginTop: "8px",
});

const RegisterForm = styled("form")({
  width: "100%",
  marginTop: "8px",
});

const RegisterButtonContainer = styled("div")({
  marginTop: "16px",
  display: "flex",
  gap: "16px",
});

const Register = () => {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const validateEmail = (email) => {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).toLowerCase());
  };

  const handleRegister = async (e) => {
    e.preventDefault();

    if (!validateEmail(email)) {
      toast.error(
        "Please enter a valid email address",
        {
          position: toast.POSITION.TOP_RIGHT,
          autoClose: 5000,
        }
      );
      return;
    }

    console.log("url " + (backend_url + "/api/register"));
    try {
      const response = await fetch(`${backend_url}/api/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
        credentials: "include",
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === "success") {
          router.push("/");
        }
      } else if (response.status === 400) {
        const data = await response.json();
        if (data.message === "Email already exists") {
          toast.error(
            "Email already exists",
            {
              position: toast.POSITION.TOP_RIGHT,
              autoClose: 5000,
            }
          );
        }
      }
    } catch (error) {
      console.error("Register error:", error);
    }
  };

  return (
    <div>
      <ToastContainer />
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
              key="password-input"
            />
            <RegisterButtonContainer>
              <Button
                type="submit"
                fullWidth
                variant="contained"
                color="primary"
              >
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