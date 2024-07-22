import React, { useState } from 'react';
import { useRouter } from 'next/router';
import { TextField, Button, Typography, Container } from '@mui/material';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import Navbar from '../components/Navbar';
import { backend_url } from '../utils/settings';

const ResetPassword = () => {
    const [email, setEmail] = useState('');
    const [token, setToken] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [step, setStep] = useState(1); // 1 for entering email, 2 for entering token, 3 for entering new password
    const router = useRouter();

    const handleRequestReset = async (e) => {
        e.preventDefault();
        try {
            const response = await fetch(`${backend_url}/api/request_password_reset`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email })
            });
            const data = await response.json();
            if (data.status === 'success') {
                toast.success('Password reset email sent.');
                setStep(2);
            } else {
                toast.error(data.message);
            }
        } catch (error) {
            toast.error('Error sending password reset email.');
        }
    };

    const handleVerifyToken = async (e) => {
        e.preventDefault();
        try {
            const response = await fetch(`${backend_url}/api/verify_token`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ token })
            });
            const data = await response.json();
            if (data.status === 'success') {
                toast.success('Token verified.');
                setStep(3);
            } else {
                toast.error(data.message);
            }
        } catch (error) {
            toast.error('Error verifying token.');
        }
    };

    const handleResendToken = async () => {
        try {
            const response = await fetch(`${backend_url}/api/request_password_reset`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email })
            });
            const data = await response.json();
            if (data.status === 'success') {
                toast.success('Password reset email resent.');
            } else {
                toast.error(data.message);
            }
        } catch (error) {
            toast.error('Error resending password reset email.');
        }
    };

    const handleResetPassword = async (e) => {
        e.preventDefault();
        try {
            const response = await fetch(`${backend_url}/api/reset_password`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ token, newPassword })
            });
            const data = await response.json();
            if (data.status === 'success') {
                toast.success('Password reset successfully.');
                router.push('/login');
            } else {
                toast.error(data.message);
            }
        } catch (error) {
            toast.error('Error resetting password.');
        }
    };

    return (
        <div>
            <Navbar />
            <Container component="main" maxWidth="xs">
                <ToastContainer />
                <Typography component="h1" variant="h5" style={{ marginTop: '1rem' }}>
                    {step === 1 ? 'Reset Password' : step === 2 ? 'Enter Token' : 'Enter New Password'}
                </Typography>
                {step === 1 && (
                    <form onSubmit={handleRequestReset}>
                        <TextField
                            variant="outlined"
                            margin="normal"
                            required
                            fullWidth
                            id="email"
                            label="Email Address"
                            name="email"
                            autoComplete="email"
                            autoFocus
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                        />
                        <Button
                            type="submit"
                            fullWidth
                            variant="contained"
                            color="primary"
                            style={{ marginTop: '1rem' }}
                        >
                            Send Reset Email
                        </Button>
                    </form>
                )}
                {step === 2 && (
                    <>
                        <form onSubmit={handleVerifyToken}>
                            <TextField
                                variant="outlined"
                                margin="normal"
                                required
                                fullWidth
                                id="token"
                                label="Token"
                                name="token"
                                autoFocus
                                value={token}
                                onChange={(e) => setToken(e.target.value)}
                            />
                            <Button
                                type="submit"
                                fullWidth
                                variant="contained"
                                color="primary"
                                style={{ marginTop: '1rem' }}
                            >
                                Verify Token
                            </Button>
                        </form>
                        <Button
                            fullWidth
                            variant="text"
                            color="primary"
                            onClick={handleResendToken}
                            style={{ marginTop: '1rem' }}
                        >
                            Resend Token
                        </Button>
                    </>
                )}
                {step === 3 && (
                    <form onSubmit={handleResetPassword}>
                        <TextField
                            variant="outlined"
                            margin="normal"
                            required
                            fullWidth
                            name="newPassword"
                            label="New Password"
                            type="password"
                            id="newPassword"
                            autoComplete="new-password"
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                        />
                        <Button
                            type="submit"
                            fullWidth
                            variant="contained"
                            color="primary"
                            style={{ marginTop: '1rem' }}
                        >
                            Reset Password
                        </Button>
                    </form>
                )}
            </Container>
        </div>
    );
};

export default ResetPassword;
