import { Box } from "@mui/material";
import Button from "@mui/material/Button";

export default function ExportButton({ onClick, filing, challenge }) {
  return (
    <Box>
      {filing && (
        <div>
          <Button
            variant="contained"
            onClick={onClick}
            style={{ marginRight: "10px" }}
          >
            Submit
          </Button>
        </div>
      )}

      {challenge && (
        <div>
          <Button
            variant="contained"
            onClick={onClick}
            style={{ marginRight: "10px" }}
          >
            Compute Challenges
          </Button>
        </div>
      )}
    </Box>
  );
}
