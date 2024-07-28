import React, { useState, useEffect } from 'react';
import { Box, Typography, Collapse, List, ListItem, ListItemText, Button, Drawer, IconButton } from '@mui/material';
import Alert from '@mui/material/Alert';
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import MenuIcon from '@mui/icons-material/Menu';
import { backend_url } from "../utils/settings";

const TaskInfo = () => {
    const [inProgressTasks, setInProgressTasks] = useState([]);
    const [finishedTasks, setFinishedTasks] = useState([]);
    const [open, setOpen] = useState(false);
    const [drawerOpen, setDrawerOpen] = useState(false);
    
    useEffect(() => {
        const fetchTasks = async () => {
            fetch(`${backend_url}/api/user-tasks`, {
                method: "GET",
                credentials: "include",
            })
                .then((response) => response.json())
                .then((data) => {
                    if (data.status === 'success') {
                        setInProgressTasks(data.in_progress_tasks);
                        setFinishedTasks(data.finished_tasks);
                    }
                })
                .catch((error) => {
                   console.log(error);
                });
        };

        fetchTasks();
        const intervalId = setInterval(fetchTasks, 5000); // Fetch every 10 seconds

        return () => clearInterval(intervalId);
    }, []);

    return (
        <Box>
            <ToastContainer />
            <Box display="flex" alignItems="center">
                <IconButton
                    size="large"
                    edge="start"
                    color="inherit"
                    aria-label="menu"
                    onClick={() => setDrawerOpen(true)}
                >
                    <MenuIcon />
                </IconButton>
                <Alert
                    severity="info"
                    onClick={() => setDrawerOpen(true)}
                    style={{ cursor: 'pointer' }}
                >
                    {`Your organization has ${inProgressTasks.length} ongoing tasks`}
                </Alert>
            </Box>
            <Drawer
                anchor="right"
                open={drawerOpen}
                onClose={() => setDrawerOpen(false)}
            >
                <Box sx={{ width: 300, padding: 2 }}>
                    <Typography variant="h6">In Progress Tasks</Typography>
                    <List>
                        {inProgressTasks.map(task => (
                            <ListItem key={task.task_id}>
                                <ListItemText
                                    primary={task.operation}
                                    secondary={`User: ${task.user}, Status: ${task.status}, Result: ${task.result}`}
                                />
                            </ListItem>
                        ))}
                    </List>
                    <Typography variant="h6">
                        Finished Tasks
                        <Button onClick={() => setOpen(!open)}>{open ? 'Hide' : 'Show'}</Button>
                    </Typography>
                    <Collapse in={open}>
                        <List>
                            {finishedTasks.map(task => (
                                <ListItem key={task.task_id}>
                                    <ListItemText
                                        primary={task.operation}
                                        secondary={`User: ${task.user}, Status: ${task.status}, Result: ${task.result}`}
                                    />
                                </ListItem>
                            ))}
                        </List>
                    </Collapse>
                </Box>
            </Drawer>
        </Box>
    );
};

export default TaskInfo;
