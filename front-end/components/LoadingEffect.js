import { Backdrop, CircularProgress, Box } from '@mui/material';
import { makeStyles } from '@mui/styles';

const useStyles = makeStyles({
    backdrop: {
        zIndex: 1200,
        color: '#fff',
    },
});

export default function LoadingEffect(isLoading) {
    const classes = useStyles();


    return (
        <div className="LoadingEffect">
            <Backdrop className={classes.backdrop} open={isLoading}>
                
                <CircularProgress color="inherit" />
            </Backdrop>
        </div>
    );
}