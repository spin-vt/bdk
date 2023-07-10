import { Backdrop, CircularProgress, Typography } from '@mui/material';
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

export default function LoadingEffect({ isLoading, loadingTimeInMs }) {
    const classes = useStyles();
    const [progress, setProgress] = useState(0);
    // const loadingTimeInMs = 3 * 60 * 1000; // 3 minutes in milliseconds
    const [isLoaded, setIsLoaded] = useState(false);

    useEffect(() => {
        let startTime = Date.now();
        let timer = null;
        console.log(isLoading);
        if (isLoading) {
            setProgress(0);
            setIsLoaded(false);
            timer = setInterval(() => {
                const timePassed = Date.now() - startTime;
                const newProgress = (timePassed / loadingTimeInMs) * 100;

                if (newProgress >= 99) {
                    clearInterval(timer);
                    setProgress(99);
                } else {
                    setProgress(newProgress);
                }
            }, 1000);
        } else {
            setProgress(100);
            setIsLoaded(true);
        }

        return () => {
            if (timer) {
                clearInterval(timer);
            }
        };
    }, [isLoading]);

    return (
        <div className="LoadingEffect">
            <Backdrop className={classes.backdrop} open={isLoading || isLoaded}>


                <CircularProgress color="inherit" variant="determinate" value={progress} />
                <div className={classes.remindertext}>
                    {isLoaded ? (
                        <Typography>Your data is ready!</Typography>
                    ) : (
                        <Typography>Crunching your data, please wait {Math.floor(progress)}%</Typography>)}
                </div>

            </Backdrop>
        </div>
    );
}