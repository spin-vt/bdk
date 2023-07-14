import * as React from "react";
import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import MenuIcon from "@mui/icons-material/Menu";
import Drawer from "@mui/material/Drawer";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import Link from "next/link";
import { Menu, MenuItem } from "@mui/material";
import { useRouter } from "next/router";
import { makeStyles } from '@material-ui/core/styles';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import HomeIcon from '@mui/icons-material/Home';
import InfoIcon from '@mui/icons-material/Info';
import BusinessIcon from '@mui/icons-material/Business';
import ContactMailIcon from '@mui/icons-material/ContactMail';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import LoginIcon from '@mui/icons-material/Login';
import UploadIcon from '@mui/icons-material/Upload';
import Searchbar from './Searchbar';
import FolderIcon from '@mui/icons-material/Folder';
// import handleDownloadClick from "./Upload"


const useStyles = makeStyles((theme) => ({
  appBar: {
    backgroundImage: 'linear-gradient(to right, #3A7BD5, #3A6073)', // Gradient color
    position: 'sticky', // Make the AppBar sticky
    boxShadow: '0px 2px 4px -1px rgb(0 0 0 / 20%), 0px 4px 5px 0px rgb(0 0 0 / 14%), 0px 1px 10px 0px rgb(0 0 0 / 12%)',
  },
  drawer: {
    width: '240px',
    flexShrink: 0,
  },
  drawerPaper: {
    width: '240px',
    backgroundColor: '#EBF5FA',  // A modern, light blue color
  },
  listItemElem: {
    display: 'flex',  // Add flex display
    alignItems: 'center',  // Vertically align items in the center
    padding: '4px',
    borderRadius: '4px',
    transition: 'background-color 0.3s',
    '&:hover': {
      backgroundColor: '#E0F7FA',
    },
  },
  iconText: {
    marginRight: '4px',  // Add right margin to the icon
    color: '#0A539E',  // Blue color for icons
  },
  button_lowercase_text: {
    textTransform: 'none',
  },
  title: {
    fontWeight: 700,  // Make the title bold
    color: '#FFFFFF',  // White color for the title
  },
  menuItem: {
    transition: 'color 0.3s',
    '&:hover': {
      color: '#3A7BD5',
    },
  },
}));

export default function Navbar({handleMyFileOpen}) {
  const router = useRouter();
  const classes = useStyles();

  function useLocalStorage(key, initialValue) {
    const [storedValue, setStoredValue] = React.useState(() => {
      try {
        if (typeof window !== undefined) {
          const item = window.localStorage.getItem(key);
          return item ? item : initialValue;
        }
        else {
          return null;
        }
      } catch (error) {
        console.error(error);
        return initialValue;
      }
    });

    const setValue = (value) => {
      try {
        if (value === null) {
          if (typeof window !== undefined) {
            window.localStorage.removeItem(key);
          }
          setStoredValue(null);
        } else {
          if (typeof window !== undefined) {
            window.localStorage.setItem(key, value);
          }
          setStoredValue(value);
        }
      } catch (error) {
        console.error(error);
      }
    };

    return [storedValue, setValue];
  }

  const searchInputRef = React.useRef(null);
  const buttonRef = React.useRef(null);
  const [username, setUsername] = useLocalStorage("username", null);
  const [isDrawerOpen, setIsDrawerOpen] = React.useState(false);

  const [anchorEl, setAnchorEl] = React.useState(null);

  const [menuOpen, setMenuOpen] = React.useState(false);
  const [menuWidth, setMenuWidth] = React.useState(null);


  const handleDownloadClick = (event) => {
    event.preventDefault();
    window.location.href = "http://localhost:5000/export";
  };

  const handleMenuOpen = (event) => {
    setMenuOpen(true);
    setAnchorEl(event.currentTarget);
    if (buttonRef.current) {
      setMenuWidth(buttonRef.current.offsetWidth);
    }
  };

  const handleMenuClose = () => {
    setMenuOpen(false);
    setAnchorEl(null);
  };

  const handleDrawerOpen = () => {
    setIsDrawerOpen(true);
  };

  const handleDrawerClose = () => {
    setIsDrawerOpen(false);
  };

  const handleLoginClick = (event) => {
    event.preventDefault(); // Prevent the default behavior
    // Navigate to the login page
  };

  const handleMenuNavigation = (link) => {
    handleMenuClose();
    router.push(link);
  };

  const handleLogout = async (e) => {
    e.preventDefault();

    try {
      const response = await fetch('http://localhost:5000/api/logout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include', // Include cookies in the request
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === "success") {
          localStorage.removeItem('username');  // Remove username from local storage
          setUsername(null);  // Update username state
          router.push('/');
        }
      } else {
        console.error('Logout failed');
      }
    } catch (error) {
      console.error('Logout error:', error);
    }
  }

  const fetchUserInfo = async () => {
    const usernameFromStorage = localStorage.getItem("username");
    console.log(usernameFromStorage);  
      try {
        const response = await fetch('http://localhost:5000/api/user', {
          method: "GET",
          credentials: "include", // Include cookies in the request
          headers: {
            Accept: "application/json",
          },
        });
        if (response.ok) {
          const data = await response.json();
          if (data.username === "") {
            setUsername(null);
            localStorage.removeItem("username");
          } else {
            setUsername(data.username);
          }
        } else {
          console.error("Fetching user info failed");
          setUsername(null); // Clear the username state variable
          localStorage.removeItem("username");
        }
      } catch (error) {
        console.error("Fetching user info error:", error);
        setUsername(null); // Clear the username state variable
        localStorage.removeItem("username");
      }
    
  };


  const [hasMounted, setHasMounted] = React.useState(false);

  React.useEffect(() => {
    setHasMounted(true);
    const fetchData = async () => {
      await fetchUserInfo();
    }

    fetchData();
  }, [username]);

  if (!hasMounted) {
    return null;
  }

  let menuTopItem;

  if (username) {
    menuTopItem = { text: 'Hello, ' + username, href: '/profile', icon: <AccountCircleIcon className={classes.icon} /> };
  } else {
    menuTopItem = { text: 'Hello, sign in', href: '/login', icon: <LoginIcon className={classes.icon} /> };
  }

  const menuItems = [
    { text: 'Home', href: '/', icon: <HomeIcon className={classes.iconText} /> },
    { text: 'About', href: '/about', icon: <InfoIcon className={classes.iconText} /> },
    { text: 'Services', href: '/services', icon: <BusinessIcon className={classes.iconText} /> },
    { text: 'Contact', href: '/contact', icon: <ContactMailIcon className={classes.iconText} /> },
  ];

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static" className={classes.appBar}>
        <Toolbar>
          <IconButton
            size="large"
            edge="start"
            color="inherit"
            aria-label="menu"
            sx={{ mr: 2 }}
            onClick={handleDrawerOpen}
          >
            <MenuIcon className={classes.menuItem} />
          </IconButton>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }} className={classes.title}>
            Broadband Data Collection Helper
          </Typography>
          <Searchbar className={classes.menuItem} />

          <IconButton onClick={handleMyFileOpen}>
            <FolderIcon sx={{ color: "white", marginRight: "5px" }} />
            <Typography component="div" sx={{ flexGrow: 1 }} className={classes.title}>
              Your Files
            </Typography>
          </IconButton>

          <IconButton href='/previousfile'>
            <UploadIcon sx={{ color: "white", marginRight: "5px" }} />
            <Typography component="div" sx={{ flexGrow: 1 }} className={classes.title} onClick={handleDownloadClick}>
              Export 
            </Typography>
          </IconButton>

          <Box display="flex" alignItems="center">
            {username ? (
              <Box display="flex" alignItems="center">
                <IconButton ref={buttonRef} color="inherit" onClick={handleMenuOpen} >
                  <AccountCircleIcon />
                  <Typography variant="body1">{username}</Typography>
                  {menuOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </IconButton>
                <Menu
                  anchorEl={anchorEl}
                  open={Boolean(anchorEl)}
                  onClose={handleMenuClose}
                  PaperProps={{
                    style: {
                      width: menuWidth,
                    },
                  }}
                >
                  <MenuItem onClick={() => handleMenuNavigation("/profile")}>
                    Profile
                  </MenuItem>
                  <MenuItem onClick={handleLogout}>
                    Logout
                  </MenuItem>
                </Menu>
              </Box>
            ) : (
              <Link href="/login">
                <Button color="inherit">
                  <LoginIcon />
                  Login
                </Button>
              </Link>
            )}
          </Box>
        </Toolbar>
      </AppBar>
      <Drawer
        anchor="left" open={isDrawerOpen}
        onClose={handleDrawerClose}
        className={classes.drawer}
        classes={{
          paper: classes.drawerPaper,
        }}>
        <List>
          <Link href={menuTopItem.href}>
            <ListItem onClick={handleDrawerClose} className={classes.listItemElem}>

              {menuTopItem.icon}
              <ListItemText primary={menuTopItem.text} />

            </ListItem>
          </Link>
          {menuItems.map((item, index) => (
            <Link href={item.href} key={item.text}>
              <ListItem onClick={handleDrawerClose} className={classes.listItemElem} >

                {item.icon}
                <ListItemText primary={item.text} />
              </ListItem>
            </Link>
          ))}
        </List>
      </Drawer>
    </Box>
  );
}
