import { useState } from "react";
import { useRouter } from "next/router";
import { TextField, Button, Typography, Container } from "@mui/material";
import Navbar from "../components/Navbar";
import Swal from "sweetalert2";
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

  const [username, setUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [providerId, setProviderId] = useState("");
  const [brandName, setBrandName] = useState("");
  const [userConfirmationCode, setUserConfirmationCode] = useState("");
  const [step, setStep] = useState(1);
  const [generatedConfirmationCode, setGeneratedConfirmationCode] =
    useState("");

  const handleRegister = async (e) => {
    e.preventDefault();

    try {
      if (step === 1) {
        // Step 1: Send the username, provider id, and brand name to the server
        const response = await fetch(`${backend_url}/api/forgot-password`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ username }),
          credentials: "include",
        });

        if (response.ok) {
          // send an email to the user's entered email address including the confirmation code

          const emailVerificationResponse = await fetch(
            `${backend_url}/api/send-confirmation-code`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({ username }),
              credentials: "include",
            }
          );

          if (emailVerificationResponse.ok) {
            const data = await emailVerificationResponse.json();
            console.log("message " + data.message);
            setGeneratedConfirmationCode(data.message);
            Swal.fire(
              "Check Email Inbox",
              "We sent you a confirmation code for verification! Do not close out or refresh this window."
            );
            setStep(2);
          } else if (response.status == 400 || response.status == 500) {
            Swal.fire(
              "Error",
              "Error sending email, please try again later",
              "error"
            );
          }
        } else if (response.status === 400) {
          const data = await response.json();
          if (
            data.message ===
            "Username, provider id, or brand name does not match"
          ) {
            Swal.fire(
              "Error",
              "Some of the provided information does not match our records. Please ensure that your username, provider ID, and brand name are correct and try again",
              "error"
            );
          }
        }
      } else if (step === 2) {
        // Step 2: Send the confirmation code to the server

        console.log(
          "Value is " +
            userConfirmationCode +
            " generated " +
            generatedConfirmationCode
        );

        if (generatedConfirmationCode == userConfirmationCode) {
          setStep(3);
        } else {
          Swal.fire("Error", "Confirmation code is incorrect", "error");
        }
      } else if (step === 3) {
        const response = await fetch(`${backend_url}/api/forgot-password`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            username,
            brandName,
            providerId,
            newPassword,
          }),
          credentials: "include",
        });

        if (response.ok) {
          router.push("/login");
        } else if (response.status === 400) {
          const data = await response.json();
          if (data.status === "error") {
            Swal.fire(
              "Error",
              "Error resetting password, please try again later!",
              "error"
            );
          }
        }
      }
    } catch (error) {
      console.error("Register error:", error);
    }
  };

  return (
    <div>
      <Navbar />
      <Container component="main" maxWidth="xs">
        <RegisterContainer>
          <Typography component="h1" variant="h5">
            Reset Password
          </Typography>
          <RegisterForm onSubmit={handleRegister} noValidate>
            {step === 1 && (
              <div>
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
              </div>
            )}

            {step === 2 && (
              <div>
                <TextField
                  variant="outlined"
                  margin="normal"
                  required
                  fullWidth
                  id="confirmationCode"
                  label="Confirmation Code"
                  name="confirmationCode"
                  value={userConfirmationCode}
                  onChange={(e) => setUserConfirmationCode(e.target.value)}
                  key="confirmationCode-input"
                />
              </div>
            )}

            {step === 3 && (
              <div>
                <TextField
                  variant="outlined"
                  margin="normal"
                  required
                  fullWidth
                  name="new_password"
                  label="New Password"
                  type="password"
                  id="new_password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  key="password-input"
                />
              </div>
            )}

            <RegisterButtonContainer>
              <Button
                type="submit"
                fullWidth
                variant="contained"
                color="primary"
              >
                {step === 1 || step === 2 ? "Next" : "Change Password"}
              </Button>
            </RegisterButtonContainer>
          </RegisterForm>
        </RegisterContainer>
      </Container>
    </div>
  );
};

export default Register;
