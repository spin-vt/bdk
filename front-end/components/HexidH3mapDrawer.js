import React, { useState, useEffect, useRef } from 'react';
import Drawer from '@mui/material/Drawer';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import Button from '@mui/material/Button';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import { cellToLatLng } from 'h3-js';
import maplibregl from "maplibre-gl";

function HexidH3mapDrawer({ mapRef }) {
    const [sortedData, setSortedData] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [page, setPage] = useState(1);
    const pageSize = 100; // Set page size for infinite scrolling
    const distinctMarkerRef = useRef(null);
    const [sortType, setSortType] = useState({ field: 'count', order: 'desc' });

    // Load initial data
    useEffect(() => {
        const dataFile = `hexid_sorted_by_${sortType.field}_${sortType.order}.json`;
        setSortedData([]); // Clear existing data
        setPage(1); // Reset to first page
        loadSortedData(dataFile);
    }, [sortType]);

    const loadSortedData = async (file) => {
        setIsLoading(true);
        const response = await fetch(file);
        const data = await response.json();
        const dataArray = Object.entries(data).map(([hexId, info]) => ({
            hexId,
            ...info,
        }));
        const newEntries = dataArray.slice((page - 1) * pageSize, page * pageSize);
        setSortedData(prevData => [...prevData, ...newEntries]);
        setIsLoading(false);
    };

    // Function to load additional data
    const loadMoreData = async () => {
        if (isLoading) return;
        setPage(prevPage => prevPage + 1);
    };

    useEffect(() => {
        if (page > 1) {
            const dataFile = `hexid_sorted_by_${sortType.field}_${sortType.order}.json`;
            loadSortedData(dataFile);
        }
    }, [page]);

    const goToHexagon = (hexId) => {
        const [latitude, longitude] = cellToLatLng(hexId);
        if (distinctMarkerRef.current) {
            distinctMarkerRef.current.remove();
        }
        distinctMarkerRef.current = new maplibregl.Marker({ color: "#FFFFFF", draggable: false })
            .setLngLat([longitude, latitude])
            .addTo(mapRef.current);
        mapRef.current.flyTo({ center: [longitude, latitude], zoom: 10, essential: true });
    };

    const handleSortOrderToggle = () => {
        // Toggle the sort order for the current field
        setSortType(prev => ({ ...prev, order: prev.order === 'desc' ? 'asc' : 'desc' }));
    };

    const handleSortFieldChange = (event) => {
        // Set the new sort field and reset order to 'desc'
        setSortType({ field: event.target.value, order: 'desc' });
    };

    return (
        <Drawer variant="permanent" anchor="right" open={true}>
            <Select
                value={sortType.field}
                onChange={handleSortFieldChange}
                fullWidth
            >
                <MenuItem value="count">Sort By: Number of Tests</MenuItem>
                <MenuItem value="throughput">Sort By: Throughput</MenuItem>
                <MenuItem value="stddev">Sort By: Standard Deviation</MenuItem>
                <MenuItem value="errorradius">Sort By: Error Radius</MenuItem>
            </Select>
            <Button onClick={handleSortOrderToggle}>
                Sort Order: {sortType.order === 'desc' ? 'Descending' : 'Ascending'}
            </Button>
            <List>
                {sortedData.map((item, index) => (
                    <ListItem key={index}>
                        <div>
                            <div>Hex ID: {item.hexId}</div>
                            <div>Number of Tests: {item.sum_count}</div>
                            <div>Sum Average Throughput: {item.sum_average_throughput.toFixed(2)}</div>
                            <div>Sum Standard Deviation Throughput: {item.sum_std_dev_throughput.toFixed(2)}</div>
                            <div>Sum Average Error Radius (KM): {item.sum_avg_error_radius_km.toFixed(2)}</div>
                            <div>Sparseness (KM): {item.sparseness_km.toFixed(2)}</div>
                            <Button onClick={() => goToHexagon(item.hexId)}>Go to Hexagon</Button>
                        </div>
                    </ListItem>
                ))}
                <ListItem>
                    <Button onClick={loadMoreData} disabled={isLoading}>
                        {isLoading ? 'Loading...' : 'Load More'}
                    </Button>
                </ListItem>
            </List>
            {isLoading && <div>Loading...</div>}
        </Drawer>
    );
}

export default HexidH3mapDrawer;
