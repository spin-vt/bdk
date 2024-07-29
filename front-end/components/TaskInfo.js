import React, { useState, useEffect, useContext } from 'react';
import { Box, Typography, Collapse, List, ListItem, ListItemText, Button, Drawer, IconButton, CircularProgress } from '@mui/material';
import Alert from '@mui/material/Alert';
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import MenuIcon from '@mui/icons-material/Menu';
import { backend_url } from "../utils/settings";
import FetchTaskInfoContext from '../contexts/FetchTaskInfoContext';
import DoneIcon from '@mui/icons-material/Done';
import ErrorIcon from '@mui/icons-material/Error';
import { green, red, grey } from '@mui/material/colors';
import ReloadMapContext from '../contexts/ReloadMapContext';

const useFetchTaskInfo = (shouldFetchTaskInfo, setShouldFetchTaskInfo, setShouldReloadMap) => {
    const [inProgressTasks, setInProgressTasks] = useState([]);
    const [finishedTasks, setFinishedTasks] = useState([]);

    useEffect(() => {
        if (!shouldFetchTaskInfo) return;

        const before_inprogress_tasks_length = inProgressTasks.length;
        const fetchTasks = async () => {
            try {
                const response = await fetch(`${backend_url}/api/user-tasks`, {
                    method: "GET",
                    credentials: "include",
                });
                const data = await response.json();
                if (data.status === 'success') {
                    setInProgressTasks(data.in_progress_tasks);
                    setFinishedTasks(data.finished_tasks);
                    const after_inprogress_tasks_length = data.in_progress_tasks.length;
                    if (before_inprogress_tasks_length > 0 && after_inprogress_tasks_length === 0) {
                        setShouldReloadMap(true);
                    }
                }
            } catch (error) {
                console.log(error);
            } finally {
                setShouldFetchTaskInfo(false);
            }
        };

        fetchTasks();
    }, [shouldFetchTaskInfo, setShouldFetchTaskInfo]);

    return { inProgressTasks, finishedTasks };
};

const fetchEstimatedRuntime = async (task_id, setShouldFetchTaskInfo) => {
    try {
        const response = await fetch(`${backend_url}/api/estimated-task-runtime/${task_id}`, {
            method: "GET",
            credentials: "include",
        });
        const data = await response.json();
        if (data.estimated_runtime === 0) {
            setShouldFetchTaskInfo(true);
            return null;
        }
        return data.estimated_runtime;
    } catch (error) {
        console.log(error);
        return null;
    }
};


const updateTaskStatus = async (task_id, status, setShouldFetchTaskInfo) => {
    try {
        await fetch(`${backend_url}/api/update-task-status/${task_id}`, {
            method: "POST",
            credentials: "include",
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ status }),
        });
        setShouldFetchTaskInfo(true);
    } catch (error) {
        console.log(error);
    }
};


const TaskInfo = () => {
    const [open, setOpen] = useState(false);
    const [drawerOpen, setDrawerOpen] = useState(false);
    const { shouldFetchTaskInfo, setShouldFetchTaskInfo } = useContext(FetchTaskInfoContext);
    const { setShouldReloadMap } = useContext(ReloadMapContext);
    const { inProgressTasks, finishedTasks } = useFetchTaskInfo(shouldFetchTaskInfo, setShouldFetchTaskInfo, setShouldReloadMap);


    useEffect(() => {
        const intervalId = setInterval(() => {
            setShouldFetchTaskInfo(true);
        }, 30000); // Set to true every 30 seconds

        return () => clearInterval(intervalId);
    }, [setShouldFetchTaskInfo]);

    const handleDrawerOpen = () => {
        setDrawerOpen(true);
        setShouldFetchTaskInfo(true);
    };

    const TaskListItem = ({ task }) => {
        const [estimatedRuntime, setEstimatedRuntime] = useState(null);
        const [elapsedTime, setElapsedTime] = useState(0);

        useEffect(() => {

            fetchEstimatedRuntime(task.task_id).then(runtime => setEstimatedRuntime(runtime));

        }, [task]);

        useEffect(() => {

            const startTime = new Date(task.start_time).getTime();
            const interval = setInterval(() => {
                setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
            }, 1000);
            return () => clearInterval(interval);

        }, [task.start_time, task.status]);

        useEffect(() => {
            if (estimatedRuntime && elapsedTime >= 2 * estimatedRuntime) {
                updateTaskStatus(task.task_id, 'FAILURE', setShouldFetchTaskInfo);
            }
        }, [elapsedTime, estimatedRuntime, task.task_id]);

        return (
            <ListItem key={task.task_id} sx={{ borderBottom: `1px solid ${grey[200]}` }}>
                <ListItemText
                    primary={
                        <Box component="span">
                            <strong>{task.user}</strong> initiate <strong>{task.operation}</strong> operation at <strong>{task.start_time}</strong>
                            {estimatedRuntime && (task.status === 'PENDING' || task.status === 'STARTED' || task.status === 'RETRY') ? (
                                <Box display="flex" alignItems="center">
                                    <CircularProgress
                                        variant="determinate"
                                        value={(elapsedTime / estimatedRuntime) * 100}
                                        size={24}
                                    />
                                    <Typography variant="body2" sx={{ ml: 1 }}>
                                        {Math.round((elapsedTime / estimatedRuntime) * 100)}%
                                    </Typography>
                                </Box>
                            ) : null}
                        </Box>
                    }

                />
            </ListItem>
        );
    };

    return (
        <Box>
            <ToastContainer />
            <Box display="flex" alignItems="center">
                <IconButton
                    size="large"
                    edge="start"
                    color="inherit"
                    aria-label="menu"
                    onClick={() => handleDrawerOpen()}
                >
                    <MenuIcon />
                </IconButton>
                {inProgressTasks.length > 0 ? (
                    <Alert
                        severity="warning"
                        onClick={() => handleDrawerOpen()}
                        style={{ cursor: 'pointer' }}
                    >
                        {`Your organization has ${inProgressTasks.length} ongoing tasks. The current map might not be accurate.`}
                    </Alert>
                ) : (
                    <Alert
                        severity="info"
                        onClick={() => handleDrawerOpen()}
                        style={{ cursor: 'pointer' }}
                    >
                        {`Your organization has 0 ongoing tasks.`}
                    </Alert>
                )}
            </Box>
            <Drawer
                anchor="right"
                open={drawerOpen}
                onClose={() => setDrawerOpen(false)}
                PaperProps={{ sx: { width: 600, p: 3 } }}
            >
                <Typography variant="h6" gutterBottom>In Progress Tasks</Typography>
                <List>
                    {inProgressTasks.map(task => (
                        <TaskListItem task={task} key={task.task_id} />
                    ))}
                </List>
                <Typography variant="h6" gutterBottom>
                    Finished Tasks
                    <Button onClick={() => setOpen(!open)} sx={{ ml: 2 }}>
                        {open ? 'Hide' : 'Show'}
                    </Button>
                </Typography>
                <Collapse in={open}>
                    <List>
                        {finishedTasks.map(task => (
                            <ListItem key={task.task_id} sx={{ borderBottom: `1px solid ${grey[200]}` }}>
                                <ListItemText
                                    primary={
                                        <Box component="span">
                                            <strong>{task.user}</strong> initiate <strong>{task.operation}</strong> operation at <strong>{task.start_time}</strong>
                                            {task.status === 'SUCCESS' && <DoneIcon sx={{ color: green[500], ml: 1 }} />}
                                            {task.status === 'FAILURE' && <ErrorIcon sx={{ color: red[500], ml: 1 }} />}
                                        </Box>
                                    }
                                />
                            </ListItem>
                        ))}
                    </List>
                </Collapse>
            </Drawer>
        </Box>
    );
};

export default TaskInfo;
