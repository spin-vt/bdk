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
  const [newPassword, setNewPassword] = useState('');
  const [providerId, setProviderId] = useState('');
  const [brandName, setBrandName] = useState('');
  const [confirmationCode, setConfirmationCode] = useState('');
  const [step, setStep] = useState(1);

  const handleRegister = async (e) => {
    e.preventDefault();

    try {
      if (step === 1) {
        // Step 1: Send the username, provider id, and brand name to the server
        const response = await fetch(`${backend_url}/api/forgot-password`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ username, providerId, brandName }),
          credentials: 'include',
        });

        if (response.ok) {
          setStep(2); // Move to the next step
        } else if (response.status === 400) {
          const data = await response.json();
          if (data.message === "Username, provider id, or brand name does not match") {
            Swal.fire('Error', 'Some of the provided information does not match our records. Please ensure that your username, provider ID, and brand name are correct and try again', 'error');
          }
        }
      } else if (step === 2) {
        // Step 2: Send the confirmation code to the server
        const response = await fetch(`${backend_url}/api/send-confirmation-code`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
        });

        if (response.ok) {
          setStep(3); // Move to the next step
        } else if (response.status === 400) {
          const data = await response.json();
          if (data.message === "Some error message") {
            Swal.fire('Error', 'Some error message', 'error');
          }
        }
      } else if (step === 3) {
        // Step 3: Send the new password to the server
        const response = await fetch(`${backend_url}/api/step-3-endpoint`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ newPassword }),
          credentials: 'include',
        });

        if (response.ok) {
          router.push("/login");
        } else if (response.status === 400) {
          const data = await response.json();
          if (data.message === "Some error message") {
            Swal.fire('Error', 'Some error message', 'error');
          }
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
                  value={confirmationCode}
                  onChange={(e) => setConfirmationCode(e.target.value)}
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
                color="primary">
                {step === 1 ? 'Next' : 'Change Password'}
              </Button>
            </RegisterButtonContainer>
          </RegisterForm>
        </RegisterContainer>
      </Container>
    </div>
  );
};

export default Register;
