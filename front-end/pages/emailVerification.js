import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button, Container, Typography, TextField, Box } from '@mui/material';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

const EmailVerification = () => {
    const { token } = useParams();
    const [showResend, setShowResend] = useState(false);

    useEffect(() => {
        fetch(`/api/verify/${token}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    toast.success(
                        "Your email have been successfully verified",
                        {
                            position: toast.POSITION.TOP_RIGHT,
                            autoClose: 5000,
                        }
                    );
                } else {
                    setShowResend(true);
                    toast.error(data.message);
                }
            });
    }, [token]);

    const resendVerification = () => {
        const email = prompt('Please enter your email address:');
        if (email) {
            fetch('/api/resend_verification', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email: email })
            })
                .then(response => response.json())
                .then(data => {
                    if (data.status === "success") {
                        toast.success(
                            "Verification email resent",
                            {
                                position: toast.POSITION.TOP_RIGHT,
                                autoClose: 5000,
                            }
                        );
                    }
                    else {
                        toast.error(
                            data.message,
                            {
                                position: toast.POSITION.TOP_RIGHT,
                                autoClose: 5000,
                            }
                        );
                    }

                });
        }
    };

    return (
        <Container maxWidth="sm" style={{ marginTop: '2rem', textAlign: 'center' }}>
            <ToastContainer />
            <Typography variant="h4" gutterBottom>Email Verification</Typography>
            {showResend && (
                <Button
                    variant="contained"
                    color="primary"
                    onClick={resendVerification}
                    style={{ marginTop: '1rem' }}
                >
                    Resend Verification Email
                </Button>
            )}
        </Container>
    );
};

export default EmailVerification;