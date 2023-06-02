import Button from '@mui/material/Button';

export default function ExportButton({ onClick }) {
  return (
    <div>
      <Button variant="contained" onClick={onClick} style={{ marginRight: '10px' }}>
        Submit
      </Button>
    </div>
  );
}
