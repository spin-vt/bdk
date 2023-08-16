import { useState } from 'react';
import { backend_url } from "../utils/settings";

function ChallengePage() {
  const [data, setData] = useState(null);

  const fetchData = async () => {
    try {
      const response = await fetch(`${backend_url}/compute-challenge`);
      const jsonData = await response.json();
      setData(jsonData);
    } catch (error) {
      console.error("Error fetching data: ", error);
    }
  }

  return (
    <div>
      <button onClick={fetchData}>Fetch Data</button>
      {data && <pre>{JSON.stringify(data, null, 4)}</pre>}
    </div>
  );
}

export default ChallengePage;
