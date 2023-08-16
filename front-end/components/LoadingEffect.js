import React, { useState, useEffect } from 'react';
import { Backdrop, CircularProgress, Typography } from '@mui/material';
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

export default function LoadingEffect({ isLoading, loadingTimeInMs }) {
    const [progress, setProgress] = useState(0);
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
            <StyledBackdrop open={isLoading || isLoaded}>
                <CircularProgress color="inherit" variant="determinate" value={progress} />
                <ReminderTextArea>
                    {isLoaded ? (
                        <Typography>Your data is ready!</Typography>
                    ) : (
                        <Typography>Crunching your data, please wait {Math.floor(progress)}%</Typography>
                    )}
                </ReminderTextArea>
            </StyledBackdrop>
        </div>
    );
}