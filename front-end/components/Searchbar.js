import React, { useState, useContext } from "react";
import TextField from "@mui/material/TextField";
import Autocomplete from "@mui/material/Autocomplete";
import CircularProgress from "@mui/material/CircularProgress";
import SelectedLocationContext from "./SelectedLocationContext";
import debounce from "lodash.debounce";

function Searchbar() {
  const [open, setOpen] = React.useState(false);
  const [options, setOptions] = React.useState([]);
  const [searchInput, setSearchInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const { setLocation } = useContext(SelectedLocationContext);
  const { location } = useContext(SelectedLocationContext);
  const handleSelectOption = (option) => {
    if (option !== undefined && option !== null) {
      setLocation({
        latitude: option.latitude,
        longitude: option.longitude,
      });
    }
  };

  // React.useEffect(() => {
  //   console.log(location); // Should log the updated location
  // }, [location]);

  const debouncedSave = React.useCallback(
    debounce((nextValue) => handleSearchChange(nextValue), 600), // debounce time of 300ms
    [] // will be created only once initially
  );

  const handleSearchChange = async (nextValue) => {
    console.log(nextValue);
    setSearchInput(nextValue);
    if (nextValue !== "") {
      setIsLoading(true);
      const response = await fetch(
        `http://localhost:8000/api/search?query=${nextValue}`
      );
      const data = await response.json();
      setTimeout(() => {
        setOptions(data);
        setIsLoading(false);
      }, 0);
      
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

  React.useEffect(() => {
    console.log(options);
  }, [options]);
  return (
    <Autocomplete
      id="searchbar"
      sx={{
        width: 400,
      }}
      open={open}
      onOpen={() => {
        setOpen(true);
      }}
      onClose={() => {
        setOpen(false);
      }}
      filterOptions={(options, params) => options}
      isOptionEqualToValue={(option, value) => 
        option.address === value.address && 
        option.city === value.city && 
        option.state === value.state && 
        option.zipcode === value.zipcode}
      getOptionLabel={(option) =>
        `${option.address}, ${option.city}, ${option.state}, ${option.zipcode}`
      }
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
  );
}

export default Searchbar;
