import React, { useState } from "react";
import Upload from "../components/Upload";
import { styled } from '@mui/material/styles';
import { Typography } from "@mui/material";

const StyledTypography = styled(Typography)({
  marginTop: "20px",
  marginBottom: "20px",
});

function UploadChallenge() {
  const [uploadChallenge, setUploadChallenge] = useState(true);

  return (
    <div>
      <StyledTypography component="h1" variant="h5" marginLeft={"1vw"}>
        Upload Challenge Data
      </StyledTypography>
      <Upload generateChallenge={uploadChallenge} />
      {/* You can further add more components or information related to the challenge upload here */}
    </div>
  );
}

export default UploadChallenge;
