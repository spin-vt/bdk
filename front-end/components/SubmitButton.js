import { Box } from "@mui/material";
import Button from "@mui/material/Button";

export default function ExportButton({ onClick, challenge }) {
  return (
    <Box>
      <div>
        <Button
          variant="contained"
          onClick={onClick}
          style={{ marginRight: "10px" }}
        >
          {challenge ? "Compute Challenges" : "Submit"}
        </Button>
      </div>
    </Box>
  );
}