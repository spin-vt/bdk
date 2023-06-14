import React, { useState } from "react";
import TextField from "@mui/material/TextField";
import Autocomplete from "@mui/material/Autocomplete";
import CircularProgress from "@mui/material/CircularProgress";


function SearchBar() {
  const [open, setOpen] = React.useState(false);
  const [options, setOptions] = React.useState([]);
  const [searchInput, setSearchInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSearchChange = async (event) => {
    setSearchInput(event.target.value);
    if (event.target.value !== "") {
        setIsLoading(true);
      const response = await fetch(
        `http://localhost:8000/api/search?query=${event.target.value}`
      );
      const data = await response.json();
      setOptions(data);
      console.log(data);
      if (data.length === 0) {
        setIsLoading(false);
      }
    } else {
      setOptions([]); // Clear the search results list
      setIsLoading(false);
      console.log(options);
    }
  };

  React.useEffect(() => {
    let active = true;

    if (!isLoading) {
      return undefined;
    }

    (async () => {
      if (active) {
        setOpen(true);
      }
    })();

    return () => {
      active = false;
    };
  }, [isLoading]);

  React.useEffect(() => {
    if (!open) {
      setOptions([]);
    }
  }, [open]);

  return (
    <Autocomplete
      id="asynchronous-demo"
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
      isOptionEqualToValue={(option, value) => option.name === value.name}
      getOptionLabel={(option) => option}
      noOptionsText="No result found"
      options={options}
      loading={isLoading}
      renderInput={(params) => (
        <TextField
          {...params}
          label="Input location id or address to search map"
          onChange={handleSearchChange}
          value={searchInput}
          sx={{
            color: 'black',
            backgroundColor: 'white',
            '& .MuiOutlinedInput-notchedOutline': {
              borderColor: 'white',
            },
            '&:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: 'white',
            },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
              borderColor: 'white',
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

export default SearchBar;
