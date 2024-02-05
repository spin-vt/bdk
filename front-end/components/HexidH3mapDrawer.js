import React, { useState, useEffect, useRef } from 'react';
import Drawer from '@mui/material/Drawer';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import Button from '@mui/material/Button';
import { cellToLatLng } from 'h3-js';
import maplibregl from "maplibre-gl";

function HexidH3mapDrawer({ mapRef }) {
    const [sortedData, setSortedData] = useState([]);
    const [dataFile, setDataFile] = useState('hexid_sorted_by_count_desc.json'); // Set default data file
    const [isLoading, setIsLoading] = useState(false);
    const [page, setPage] = useState(1);
    const pageSize = 100; // Set page size for infinite scrolling
    const distinctMarkerRef = useRef(null);

    const [sortType, setSortType] = useState({ field: 'count', order: 'desc' });

    // Load initial data
    useEffect(() => {
        loadSortedData(dataFile);
    }, [dataFile]);

    const loadSortedData = async (file) => {
        setIsLoading(true);
        const response = await fetch(file);
        const data = await response.json();
        // Convert the object to an array of objects
        const dataArray = Object.entries(data).map(([hexId, info]) => ({
            hexId,
            ...info,
        }));
        // Implement a mechanism to load more data as needed, considering dataArray is now an array
        const newEntries = dataArray.slice((page - 1) * pageSize, page * pageSize);
        setSortedData(prevData => [...prevData, ...newEntries]);
        setIsLoading(false);
    };

    // Function to load additional data
    const loadMoreData = async () => {
        if (isLoading) return; // Prevent multiple load requests
        setIsLoading(true);
        setPage(prevPage => prevPage + 1);
        const response = await fetch(dataFile);
        const newData = await response.json();
        const dataArray = Object.entries(newData).map(([hexId, info]) => ({
            hexId,
            ...info,
        }));
        const newEntries = dataArray.slice(page * pageSize, (page + 1) * pageSize);
        setSortedData(prevData => [...prevData, ...newEntries]);
        setIsLoading(false);
    };

    useEffect(() => {
        if (page > 1) {
            loadSortedData(dataFile); // Load more data when page changes, after the initial load
        }
    }, [page]);



    const goToHexagon = (hexId) => {
        // Convert the hex ID to a latitude and longitude
        const [latitude, longitude] = cellToLatLng(hexId);

        if (distinctMarkerRef.current) {
            distinctMarkerRef.current.remove();
        }

        distinctMarkerRef.current = new maplibregl.Marker({
            color: "#FFFFFF",
            draggable: false,
        })
            .setLngLat([longitude, latitude])
            .addTo(mapRef.current);

        // Use the current map reference to initiate a flyTo to the hexagon's center
        mapRef.current.flyTo({
            center: [longitude, latitude],
            zoom: [10],
            essential: true // This ensures the animation occurs even if the user has a preference set that reduces motion
        });
    };

    const handleSortToggle = (field) => {
        // Determine the new order. If the field is the same as the current sortType.field,
        // toggle the order; otherwise, set it to 'desc'.
        const order = sortType.field === field && sortType.order === 'desc' ? 'asc' : 'desc';
    
        // Set the new sort type
        const newSortType = { field, order };
    
        // Update the sortType state
        setSortType(newSortType);
    
        // Construct the new filename based on the new sort type
        const newFile = `hexid_sorted_by_${field}_${order}.json`;
    
        // Update state to trigger new data loading
        setDataFile(newFile);
        setSortedData([]);
        setPage(1);
        // Assuming loadSortedData is your function to load and set data
        loadSortedData(newFile); // Load the initial data based on the new sort type
    };
    



    return (
        <Drawer
            variant="permanent"
            anchor="right"
            open={true}
        >
            <Button onClick={() => handleSortToggle('count')}>
                Sort by Count ({sortType.field === 'count' ? (sortType.order === 'desc' ? 'Ascending' : 'Descending') : 'Toggle'})
            </Button>
            <Button onClick={() => handleSortToggle('throughput')}>
                Sort by Throughput ({sortType.field === 'throughput' ? (sortType.order === 'desc' ? 'Ascending' : 'Descending') : 'Toggle'})
            </Button>
            <List>
                {sortedData.map((item, index) => (
                    <ListItem key={index}>
                        <div>
                            <div>Hex ID: {item.hexId}</div>
                            <div>Sum Count: {item.sum_count}</div>
                            <div>Sum Average Throughput: {item.sum_average_throughput.toFixed(2)}</div>
                            <Button onClick={() => goToHexagon(item.hexId)}>Go to Hexagon</Button>
                        </div>
                    </ListItem>
                ))}
                <ListItem>
                    <Button onClick={loadMoreData} disabled={isLoading}>
                        {isLoading ? 'Loading...' : 'Load More'}
                    </Button>
                </ListItem>
                {isLoading && <div>Loading...</div>}
            </List>
        </Drawer>
    );
}

export default HexidH3mapDrawer;