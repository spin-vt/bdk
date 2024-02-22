import React, { useState } from "react";
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
import { styled } from "@mui/material/styles";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import HomeIcon from "@mui/icons-material/Home";
import InfoIcon from "@mui/icons-material/Info";
import AccountCircleIcon from "@mui/icons-material/AccountCircle";
import LoginIcon from "@mui/icons-material/Login";
import UploadIcon from "@mui/icons-material/Upload";
import DownloadIcon from "@mui/icons-material/Download";
import Searchbar from "./Searchbar";
import FolderIcon from "@mui/icons-material/Folder";
import EditIcon from "@mui/icons-material/Edit";
import CellTowerIcon from '@mui/icons-material/CellTower';
import EditMapContext from "../contexts/EditMapContext";
import { backend_url } from "../utils/settings";
import HistoryIcon from '@mui/icons-material/History';
import Swal from "sweetalert2";


const StyledAppBar = styled(AppBar)({
  backgroundImage: "linear-gradient(to right, #3A7BD5, #3A6073)",
  position: "sticky",
  boxShadow:
    "0px 2px 4px -1px rgb(0 0 0 / 20%), 0px 4px 5px 0px rgb(0 0 0 / 14%), 0px 1px 10px 0px rgb(0 0 0 / 12%)",
});

const StyledDrawer = styled(Drawer)({
  display: "flex",
  flexDirection: "column",
  justifyContent: "center",
  width: "240px",
  flexShrink: 0,
  ".MuiDrawer-paper": {
    width: "240px",
    backgroundColor: "#EBF5FA",
  },
});

const StyledListItem = styled(ListItem)({
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  padding: "4px",
  borderRadius: "4px",
  transition: "background-color 0.3s",
  "&:hover": {
    backgroundColor: "#E0F7FA",
  },
});

const TitleTypography = styled(Typography)({
  fontWeight: 700,
  color: "#FFFFFF",
  flexGrow: 1,
});

export default function Navbar({
  handleMyFileOpen,
  handleUploadOpen,
  showOnHome,
  uploadChallenge
}) {
  const router = useRouter();
  const [anchorEl, setAnchorEl] = useState(null);
  const [profileAnchorEl, setProfileAnchorEl] = useState(null);
  const isMenuOpen = Boolean(anchorEl);

  const { isEditingMap, setEditingMap } = React.useContext(EditMapContext);

  const handleEditToolClick = () => {
    setEditingMap(!isEditingMap); // <-- toggle isEditing state
  };

  function useLocalStorage(key, initialValue) {
    const [storedValue, setStoredValue] = React.useState(() => {
      try {
        if (typeof window !== undefined) {
          const item = window.localStorage.getItem(key);
          return item ? item : initialValue;
        } else {
          return null;
        }
      } catch (error) {
        console.error(error);
        Swal.fire('Error', 'Oops, looks like we hit an error on our end, please try again later', 'error');

        
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
        Swal.fire('Error', 'Oops, looks like we hit an error on our end, please try again later', 'error');

      }
    };

    return [storedValue, setValue];
  }

  const searchInputRef = React.useRef(null);
  const buttonRef = React.useRef(null);
  const [username, setUsername] = useLocalStorage("username", null);
  const [isDrawerOpen, setIsDrawerOpen] = React.useState(false);

  const [menuOpen, setMenuOpen] = React.useState(false);
  const [menuWidth, setMenuWidth] = React.useState(null);

  const handleDownloadClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = (option) => {
    setAnchorEl(null);

    if (option === 1) {
      downloadFiling();
    } else if (option === 2) {
      downloadChallenge();
    }
  };

  const downloadFiling = () => {
    window.location.href = `${backend_url}/api/exportFiling`;
  };

  const downloadChallenge = () => {
    window.location.href = `${backend_url}/api/exportChallenge`;
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
      const response = await fetch(`${backend_url}/api/logout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include", // Include cookies in the request
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === "success") {
          localStorage.removeItem("username"); // Remove username from local storage
          setUsername(null); // Update username state
          router.push("/");
        }
      } else {
        console.error("Logout failed");
      }
    } catch (error) {
      console.error("Logout error:", error);
      Swal.fire('Error', 'Error logging out', 'error');

    }
  };

  const fetchUserInfo = async () => {
    const usernameFromStorage = localStorage.getItem("username");
    console.log(usernameFromStorage);
    try {
      const response = await fetch(`${backend_url}/api/user`, {
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
      Swal.fire('Error', 'Error fetching profile info', 'error');

    }
  };

  const [hasMounted, setHasMounted] = React.useState(false);

  React.useEffect(() => {
    setHasMounted(true);
    const fetchData = async () => {
      await fetchUserInfo();
    };

    fetchData();
  }, [username]);

  if (!hasMounted) {
    return null;
  }

  let menuTopItem;

  if (username) {
    menuTopItem = {
      text: " Hello, " + username,
      href: "/profile",
      icon: <AccountCircleIcon />,
    };
  } else {
    menuTopItem = {
      text: "Hello, sign in",
      href: "/login",
      icon: <LoginIcon />,
    };
  }

  const menuItems = [
    {
      text: "Filing Tool",
      href: "/",
      icon: <HomeIcon />,
    },
    {
      text: "Wireless Coverage Calculation",
      href: "/wirelessextension",
      icon: <CellTowerIcon />,
    },
    {
      text: "Export History",
      href: "/previousexport",
      icon: <HistoryIcon />,
    },
    {
      text: "Challenge Tool",
      href: "/challenge",
      icon: <InfoIcon />,
    },
  ];

  return (
    <Box sx={{ flexGrow: 1 }}>
      <StyledAppBar position="static">
        <Toolbar>
          <IconButton
            size="large"
            edge="start"
            color="inherit"
            aria-label="menu"
            sx={{ mr: 2 }}
            onClick={handleDrawerOpen}
          >
            <MenuIcon
              sx={{
                transition: "color 0.3s",
                "&:hover": {
                  color: "#3A7BD5",
                },
              }}
            />
          </IconButton>

          <Link
            href="/"
            component="div"
            sx={{ fontWeight: "700", color: "#FFFFFF" }}
          >
            <Typography variant="h6" sx={{ marginRight: "4vw" }}>
              BDK Project
            </Typography>
          </Link>

          <Searchbar />

          {showOnHome && (
            <IconButton onClick={handleEditToolClick}>
              <EditIcon
                sx={{ fontWeight: "700", color: "white", marginRight: "5px" }}
              />
              <Typography sx={{ color: "white" }}>
                {isEditingMap ? "Exit Editing Tool" : "Editing Tool"}
              </Typography>
            </IconButton>
          )}

          {isEditingMap && (
            <IconButton onClick={handleMyFileOpen}>
              <FolderIcon
                sx={{ fontWeight: "700", color: "white", marginRight: "5px" }}
              />
              <Typography sx={{ color: "white" }}>Your Edits</Typography>
            </IconButton>
          )}

          {!isEditingMap && (
            <IconButton onClick={handleMyFileOpen}>
              <FolderIcon sx={{ color: "white", marginRight: "5px" }} />
              <Typography sx={{ color: "white" }}>Your Files</Typography>
            </IconButton>
          )}

          {!isEditingMap && (
            <IconButton onClick={handleUploadOpen}>
              <UploadIcon sx={{ color: "white", marginRight: "5px" }} />
              <Typography sx={{ color: "white" }}>Upload</Typography>
            </IconButton>
          )}

          <div>
            {!isEditingMap && (
              <IconButton onClick={handleDownloadClick}>
                <DownloadIcon sx={{ color: "white", marginRight: "5px" }} />
                <Typography sx={{ color: "white" }}>Export</Typography>
              </IconButton>
            )}

            <Menu
              anchorEl={anchorEl}
              open={isMenuOpen}
              onClose={() => handleClose()}
            >
              <MenuItem onClick={() => handleClose(1)}>BDC Filing</MenuItem>
              <MenuItem onClick={() => handleClose(2)}>
                BDC Bulk Challenge
              </MenuItem>
            </Menu>
          </div>

          <Box display="flex" alignItems="center">
            {username ? (
              <Box display="flex" alignItems="center">
                <IconButton
                  ref={buttonRef}
                  color="inherit"
                  onClick={(e) => setProfileAnchorEl(e.currentTarget)} // Use the setProfileAnchorEl here.
                >
                  <AccountCircleIcon />
                  <Typography variant="body1">{username}</Typography>
                  {menuOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </IconButton>
                <Menu
                  anchorEl={profileAnchorEl} // Use profileAnchorEl for this dropdown.
                  open={Boolean(profileAnchorEl)} // Check if profileAnchorEl is not null.
                  onClose={() => setProfileAnchorEl(null)} // Reset profileAnchorEl to null on close.
                >
                  <MenuItem onClick={() => handleMenuNavigation("/profile")}>
                    Profile
                  </MenuItem>
                  <MenuItem onClick={handleLogout}>Logout</MenuItem>
                </Menu>
              </Box>
            ) : (
              <IconButton onClick={() => router.push("/login")}>
                <LoginIcon sx={{ color: "white", marginRight: "5px" }} />
                <Typography sx={{ color: "white" }}>Login</Typography>
              </IconButton>
            )}
          </Box>
        </Toolbar>
      </StyledAppBar>
      <StyledDrawer
        anchor="left"
        open={isDrawerOpen}
        onClose={handleDrawerClose}
      >
        <List>
          <Link href={menuTopItem.href}>
            <StyledListItem onClick={handleDrawerClose}>
              {menuTopItem.icon}
              <ListItemText primary={menuTopItem.text} />
            </StyledListItem>
          </Link>
          {menuItems.map((item, index) => (
            <Link href={item.href} key={item.text}>
              <StyledListItem onClick={handleDrawerClose}>
                {item.icon}
                <ListItemText primary={item.text} />
              </StyledListItem>
            </Link>
          ))}
        </List>
      </StyledDrawer>
    </Box>
  );
}
