import { useEffect, useState } from "react";
import Navbar from '../components/Navbar';
import { Button, Container, Typography, TextField, Paper, Grid, Divider, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from '@mui/material';
import { ToastContainer, toast } from 'react-toastify';
import "react-toastify/dist/ReactToastify.css";
import { useRouter } from "next/router";
import { backend_url } from "../utils/settings";



const Profile = () => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState('');
  const [showTokenField, setShowTokenField] = useState(false);
  const [openCreateOrg, setOpenCreateOrg] = useState(false);
  const [openJoinOrg, setOpenJoinOrg] = useState(false);

  const [email, setEmail] = useState('');
  const [orgName, setOrgName] = useState('');
  const [joinOrgToken, setJoinOrgToken] = useState('');
  const router = useRouter();

  const [providerId, setProviderId] = useState('');
  const [brandName, setBrandName] = useState('');


  // State for confirming exit/delete action
  const [openConfirmDialog, setOpenConfirmDialog] = useState(false);

  // Function to handle the confirm action
  const handleConfirmAction = () => {
    if (user.is_admin) {
      deleteOrganization();
    } else {
      exitOrganization();
    }
    setOpenConfirmDialog(false);
  };

  // Function to open the confirm dialog
  const handleOpenConfirmDialog = () => {
    setOpenConfirmDialog(true);
  };

  // Function to close the confirm dialog
  const handleCloseConfirmDialog = () => {
    setOpenConfirmDialog(false);
  };


  const deleteOrganization = () => {
    fetch(`${backend_url}/api/delete_organization`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ organizationName: user.organization.organization_name }),
      credentials: 'include',
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          toast.success("Organization deleted successfully!");
          setUser({ ...user, organization: null });
        } else {
          toast.error(data.message);
        }
      })
      .catch(error => {
        console.error('Error deleting organization:', error);
        toast.error('Network error or server issue');
      });
  };

  const exitOrganization = () => {
    fetch(`${backend_url}/api/exit_organization`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ organizationName: user.organization.organization_name }),
      credentials: 'include',
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          toast.success("Exited organization successfully!");
          setUser({ ...user, organization: null });
        } else {
          toast.error(data.message);
        }
      })
      .catch(error => {
        console.error('Error exiting organization:', error);
        toast.error('Network error or server issue');
      });
  };

  const validateEmail = (email) => {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).toLowerCase());
  };

  const updateOrganizationDetails = () => {
    if (!providerId && !brandName && !email && !orgName) {
      toast.error("Please fill in the required fields");
      return;
    }

    if (!validateEmail(email)) {
      toast.error("Please enter a valid email address");
      return;
    }

    const emailUpdated = user.email !== email;
    fetch(`${backend_url}/api/update_profile`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        email: email,
        organizationName: orgName,
        providerId: providerId,
        brandName: brandName
      }),
      credentials: 'include',
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          toast.success("Profile updated successfully!");
          setUser({
            ...user,
            email: email,
            verified: emailUpdated ? false : user.verified,
            organization: {
              ...user.organization,
              organization_name: orgName,
              provider_id: providerId,
              brand_name: brandName
            }
          });
        } else {
          toast.error(data.message);
        }
      });
  };

  useEffect(() => {
    fetch(`${backend_url}/api/user`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          setUser(data.userinfo);
          setEmail(data.userinfo.email || '');
          if (data.userinfo.organization) {
            setProviderId(data.userinfo.organization.provider_id || '');
            setBrandName(data.userinfo.organization.brand_name || '');
            setOrgName(data.userinfo.organization.organization_name || '');
          }
        } else {
          toast.error("Failed to fetch user data");
          router.push('/login');
        }
      })
      .catch(error => {
        console.error("Fetch error:", error);
        toast.error("Network error or server issue");
      });
  }, []);



  const handleOpenCreateOrg = () => {
    setOpenCreateOrg(true);
  };

  const handleCloseCreateOrg = () => {
    setOpenCreateOrg(false);
  };

  const handleCreateOrg = () => {
    if (!user.verified) {
      toast.error("Please verify your email address before creating an organization");
      return;
    }
    if (!orgName) {
      toast.error("Please enter an organization name.");
      return;
    }
    fetch(`${backend_url}/api/create_organization`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ orgName: orgName }),
      credentials: 'include',
    }).then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          toast.success("Organization created successfully!");
          setUser({ ...user, organization: { organization_name: orgName } });
        } else {
          toast.error(data.message);
        }
        handleCloseCreateOrg();
      });
  };

  const handleJoinOrg = () => {
    if (!orgName) {
      toast.error("Please enter an organization name.");
      return;
    }
    fetch(`${backend_url}/api/join_organization`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ name: orgName }),
      credentials: 'include',
    }).then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          toast.success("Join request sent to organization admin.");
          setShowTokenField(true);
        } else {
          toast.error(data.message);
        }
        handleCloseJoinOrg();
      });
  };

  const handleOpenJoinOrg = () => {
    setOpenJoinOrg(true);
  };

  const handleCloseJoinOrg = () => {
    setOpenJoinOrg(false);
  };

  const resendVerification = () => {
    if (!user || !user.email) {
      toast.error("User email not available");
      return;
    }
    fetch(`${backend_url}/api/send_email_verification`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ email: user.email })
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === "success") {
          toast.success("Verification email resent");
          setShowTokenField(true);
        } else {
          toast.error(data.message);
        }
      });
  };

  const handleVerifyToken = (e) => {
    e.preventDefault();
    fetch(`${backend_url}/api/verify_token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ token })
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          toast.success('Email address verified successfully.');
          setShowTokenField(false);
          setUser({ ...user, verified: true });
        } else {
          toast.error(data.message);
        }
      })
      .catch(error => {
        console.error('Error verifying token:', error);
        toast.error('Network error or server issue');
      });
  };

  const handleVerifyJoinOrgToken = (e) => {
    e.preventDefault();
    fetch(`${backend_url}/api/verify_token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ token: joinOrgToken })
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          toast.success(`Joined ${orgName} successfully.`);
          setShowTokenField(false);
          setUser({ ...user, organization: { organization_name: orgName } });
        } else {
          toast.error(data.message);
        }
      })
      .catch(error => {
        console.error('Error verifying token:', error);
        toast.error('Network error or server issue');
      });
  };

  if (!user) return <div>Loading...</div>;

  return (
    <div>
      <Navbar />

      <Container component="main" maxWidth="md">
        <ToastContainer />
        <Grid container spacing={2} direction="column">
          {/* User Account Info Section */}
          <Grid item xs={12}>
            <Paper style={{ padding: 16 }}>
              <Typography variant="h6" gutterBottom>
                User Account Info
              </Typography>
              <Divider />
              <TextField
                label="Email"
                variant="outlined"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                fullWidth
                margin="normal"
              />
              {!user.verified && (
                <>
                  <Typography color="error" style={{ marginTop: 16 }}>
                    Your account is not verified. Please verify your email.
                  </Typography>
                  <Button variant="contained" color="primary" onClick={resendVerification} style={{ marginTop: 8 }}>
                    Send Verification Email
                  </Button>
                  {showTokenField && (
                    <form onSubmit={handleVerifyToken} style={{ marginTop: 16 }}>
                      <TextField
                        variant="outlined"
                        margin="normal"
                        required
                        fullWidth
                        id="token"
                        label="Verification Token"
                        name="token"
                        autoFocus
                        value={token}
                        onChange={(e) => setToken(e.target.value)}
                      />
                      <Button
                        type="submit"
                        fullWidth
                        variant="contained"
                        color="primary"
                        style={{ marginTop: '1rem' }}
                      >
                        Verify Token
                      </Button>
                    </form>
                  )}
                </>
              )}
            </Paper>
          </Grid>

          {/* Organization Info Section */}
          <Grid item xs={12}>
            <Paper style={{ padding: 16 }}>
              <Typography variant="h6" gutterBottom>
                Organization Info
              </Typography>
              <Divider />
              {user.organization ? (
                <>
                  {user.is_admin &&

                    <Typography variant="body1" sx={{ color: '#429e64', marginTop: '10px' }}>
                      You are the admin of the organization
                    </Typography>
                  }
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={6}>
                      <TextField
                        label="Organization Name"
                        variant="outlined"
                        value={orgName}
                        onChange={(e) => setOrgName(e.target.value)}
                        fullWidth
                        margin="normal"
                      />
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <TextField
                        label="Provider ID"
                        variant="outlined"
                        value={providerId}
                        onChange={(e) => setProviderId(e.target.value)}
                        fullWidth
                        margin="normal"
                      />
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <TextField
                        label="Brand Name"
                        variant="outlined"
                        value={brandName}
                        onChange={(e) => setBrandName(e.target.value)}
                        fullWidth
                        margin="normal"
                      />
                    </Grid>
                  </Grid>
                </>
              ) : (
                <>
                  <Typography variant="body1" style={{ marginTop: 16 }}>
                    Associate your account with an organization to start working on filings via:
                  </Typography>
                  <Button variant="contained" color="primary" onClick={handleOpenCreateOrg} style={{ marginTop: 16 }}>
                    Create an Organization
                  </Button>
                  <Button variant="contained" color="secondary" onClick={handleOpenJoinOrg} style={{ marginLeft: 10, marginTop: 16 }}>
                    Join an Organization
                  </Button>
                  {showTokenField && (
                    <form onSubmit={handleVerifyJoinOrgToken} style={{ marginTop: 16 }}>
                      <TextField
                        variant="outlined"
                        margin="normal"
                        required
                        fullWidth
                        id="joinOrgToken"
                        label="Organization Join Token"
                        name="joinOrgToken"
                        autoFocus
                        value={joinOrgToken}
                        onChange={(e) => setJoinOrgToken(e.target.value)}
                      />
                      <Button
                        type="submit"
                        fullWidth
                        variant="contained"
                        color="primary"
                        style={{ marginTop: '1rem' }}
                      >
                        Verify Token
                      </Button>
                    </form>
                  )}
                </>
              )}
            </Paper>
          </Grid>
          <Grid item xs={12}>
            {/* <Paper style={{ padding: 16 }}> */}
            <Button variant="contained" color="primary" onClick={updateOrganizationDetails}>
              Update Info
            </Button>
            {user.organization &&
              <Button variant="contained" color="secondary" onClick={handleOpenConfirmDialog} sx={{ marginLeft: 10 }}>
                {user.is_admin ? 'Delete Organization' : 'Exit Organization'}
              </Button>
            }
            {/* </Paper> */}
          </Grid>
        </Grid>
      </Container>

      <Dialog
        open={openConfirmDialog}
        onClose={handleCloseConfirmDialog}
      >
        <DialogTitle>{user.is_admin ? 'Delete Organization' : 'Exit Organization'}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to {user.is_admin ? 'delete this organization? All your filings will also be deleted.' : 'exit this organization?'} This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseConfirmDialog} color="primary">
            Cancel
          </Button>
          <Button onClick={handleConfirmAction} color="secondary">
            Confirm
          </Button>
        </DialogActions>
      </Dialog>

      {/* Create Organization Dialog */}
      <Dialog open={openCreateOrg} onClose={handleCloseCreateOrg}>
        <DialogTitle>Create an Organization</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            id="orgName"
            label="Organization Name"
            type="text"
            fullWidth
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseCreateOrg} color="primary">
            Cancel
          </Button>
          <Button onClick={handleCreateOrg} color="primary">
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {/* Join Organization Dialog */}
      <Dialog open={openJoinOrg} onClose={handleCloseJoinOrg}>
        <DialogTitle>Join an Organization</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            id="orgName"
            label="Organization Name"
            type="text"
            fullWidth
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseJoinOrg} color="primary">
            Cancel
          </Button>
          <Button onClick={handleJoinOrg} color="primary">
            Join
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
};

export default Profile;
