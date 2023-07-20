import { Backdrop, Typography, Box, CircularProgress } from '@mui/material';
import { makeStyles } from '@mui/styles';
import React, { useState, useEffect } from 'react';

const useStyles = makeStyles({
    backdrop: {
        zIndex: 1200,
        color: '#fff',
        position: 'absolute',
        minWidth: '100%',
        minHeight: '100%',
    },
    remindertext: {
        marginLeft: '10px',
    }
});

export default function SmallLoadingEffect({ isLoading }) {
    const classes = useStyles();

    return (
        <div className="LoadingEffect">
            <Backdrop className={classes.backdrop} open={isLoading}>
                <Box display="flex" alignItems="center">
                    <CircularProgress color="inherit" />
                    <div className={classes.remindertext}>
                        <Typography>Getting the editing tool ready...</Typography>
                    </div>
                </Box>
            </Backdrop>
        </div>
    );
}