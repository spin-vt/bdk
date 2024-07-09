import React, { useState, useContext } from "react";
import TextField from "@mui/material/TextField";
import Autocomplete from "@mui/material/Autocomplete";
import CircularProgress from "@mui/material/CircularProgress";
import SelectedLocationContext from "../contexts/SelectedLocationContext";
import debounce from "lodash.debounce";
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import { stateList } from "../utils/FactSheets";
import { styled } from '@mui/material/styles';
import Box from "@mui/material/Box";
import { backend_url } from "../utils/settings";
import {useFolder} from "../contexts/FolderContext.js";


const IOSSwitch = styled((props) => (
  <Switch focusVisibleClassName=".Mui-focusVisible" disableRipple {...props} />
))(({ theme }) => ({
  width: 42,
  height: 26,
  padding: 0,
  '& .MuiSwitch-switchBase': {
    padding: 0,
    margin: 2,
    transitionDuration: '300ms',
    '&.Mui-checked': {
      transform: 'translateX(16px)',
      color: '#fff',
      '& + .MuiSwitch-track': {
        backgroundColor: theme.palette.mode === 'dark' ? '#2ECA45' : '#65C466',
        opacity: 1,
        border: 0,
      },
      '&.Mui-disabled + .MuiSwitch-track': {
        opacity: 0.5,
      },
    },
    '&.Mui-focusVisible .MuiSwitch-thumb': {
      color: '#33cf4d',
      border: '6px solid #fff',
    },
    '&.Mui-disabled .MuiSwitch-thumb': {
      color:
        theme.palette.mode === 'light'
          ? theme.palette.grey[100]
          : theme.palette.grey[600],
    },
    '&.Mui-disabled + .MuiSwitch-track': {
      opacity: theme.palette.mode === 'light' ? 0.7 : 0.3,
    },
  },
  '& .MuiSwitch-thumb': {
    boxSizing: 'border-box',
    width: 22,
    height: 22,
  },
  '& .MuiSwitch-track': {
    borderRadius: 26 / 2,
    backgroundColor: theme.palette.mode === 'light' ? '#E9E9EA' : '#39393D',
    opacity: 1,
    transition: theme.transitions.create(['background-color'], {
      duration: 500,
    }),
  },
}));

function Searchbar() {
  const [open, setOpen] = React.useState(false);
  const [options, setOptions] = React.useState([]);
  const [searchInput, setSearchInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const { setLocation } = useContext(SelectedLocationContext);

  const [searchByState, setSearchByState] = useState(false);

  const {folderID, setFolderID} = useFolder();



  // handle switch change
  const handleSwitchChange = (event) => {
    setSearchByState(event.target.checked);
    setSearchInput(""); // reset search input
    setOptions([]); // reset options
    handleSelectOption(null);
  };

  const handleSelectOption = (option) => {
    if (option !== undefined && option !== null) {
      setLocation({
        latitude: option.latitude,
        longitude: option.longitude,
        zoomlevel: searchByState ? 7 : 16
      });
    }
    else {
      setLocation(null);
    }
  };

  const debouncedSave = React.useCallback(
    debounce((nextValue) => handleSearchChange(nextValue), 600), // debounce time of 600ms
    [searchByState] // will be created only once initially
  );

  const handleSearchChange = async (nextValue) => {
    if (folderID === -1) {
      return;
    }
    setSearchInput(nextValue);

    if (nextValue !== "") {
      setIsLoading(true);
      console.log(searchByState);

      if (searchByState) {
        const filteredStates = stateList.filter(state =>
          state.name.toLowerCase().includes(nextValue.toLowerCase()) ||
          state.abbreviation.toLowerCase().includes(nextValue.toLowerCase())
        );
        console.log(filteredStates);
        setTimeout(() => {
          setOptions(filteredStates);
          setIsLoading(false);
        }, 0);
      } else {
        // Modified URL to include folderID in the request
        const response = await fetch(`${backend_url}/api/search/${folderID}?query=${nextValue}`, {
          credentials: 'include'
        });
        const data = await response.json();
        setTimeout(() => {
          setOptions(data);
          setIsLoading(false);
        }, 0);
      }
    } else {
      setOptions([]); // Clear the search results list
      setIsLoading(false);
    }
};

  React.useEffect(() => {
    if (!open) {
      setOptions([]);
    }
  }, [open]);

  const isOptionEqualToValue = searchByState
    ? (option, value) => option.name === value.name
    : (option, value) => option.address === value.address &&
      option.city === value.city &&
      option.state === value.state &&
      option.zipcode === value.zipcode;

  const getOptionLabel = (option) => {
    if (!option) {
      return '';
    }

    if (searchByState) {
      return option.name ? `${option.name} (${option.abbreviation || ''})` : '';
    } else {
      let labelParts = [option.address, option.city, option.state, option.zipcode];
      // filter out empty parts and join the rest with commas
      return labelParts.filter(Boolean).join(', ');
    }
  };

  return (
    <Box sx={{ width: '600px', display: "flex", alignItems: "center" }}>
      <FormControlLabel
        control={<IOSSwitch sx={{ m: 1 }} checked={searchByState} onChange={handleSwitchChange} />}
        label="Search By State"
      />
      <Autocomplete
        id="searchbar"
        sx={{
          width: '400px',
        }}
        open={open}
        onOpen={() => {
          setOpen(true);
        }}
        onClose={() => {
          setOpen(false);
        }}
        filterOptions={(options, params) => options}
        isOptionEqualToValue={isOptionEqualToValue}
        getOptionLabel={getOptionLabel}
        onChange={(_, value) => handleSelectOption(value)}
        noOptionsText="No result found"
        options={options}
        loading={isLoading}
        renderInput={(params) => (
          <TextField
            {...params}
            placeholder="Enter address to search for location on map"
            onChange={(event) => debouncedSave(event.target.value)} // Use debounced function
            value={searchInput}
            sx={{
              color: "black",
              backgroundColor: "white",
              "& .MuiOutlinedInput-notchedOutline": {
                borderColor: "white",
              },
              "&:hover .MuiOutlinedInput-notchedOutline": {
                borderColor: "white",
              },
              "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
                borderColor: "white",
              },
            }}
            InputProps={{
              ...params.InputProps,
              endAdornment: (
                <React.Fragment>
                  {isLoading ? (
                    <CircularProgress color="inherit" size={20} />
                  ) : null}
                  {params.InputProps.endAdornment}
                </React.Fragment>
              ),
            }}
          />
        )}
      />
    </Box>
  );
}

export default Searchbar;
