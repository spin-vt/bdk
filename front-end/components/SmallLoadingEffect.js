import { Backdrop, Typography, Box, CircularProgress } from '@mui/material';
import React from 'react';
import { styled } from '@mui/material/styles';

const StyledBackdrop = styled(Backdrop)(({ theme }) => ({
    zIndex: 1200,
    position: 'fixed',
    color: '#fff',
    minWidth: '100%',
    minHeight: '100%',
}));

const ReminderTextArea = styled('div')({
    marginLeft: '10px',
});

export default function SmallLoadingEffect({ isLoading }) {

    return (
        <div className="LoadingEffect">
            <StyledBackdrop open={isLoading}>
                <Box display="flex" alignItems="center">
                    <CircularProgress color="inherit" />
                    <ReminderTextArea>
                        <Typography>Getting the editing tool ready...</Typography>
                    </ReminderTextArea>
                </Box>
            </StyledBackdrop>
        </div>
    );
}