import React from 'react';
import { styled } from "@mui/material/styles";
import { Typography } from '@mui/material';

const LegendContainer = styled('div')({
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
    position: 'absolute',
    left: '10px',
    bottom: '10px',
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
    padding: '10px',
    borderRadius: '4px',
    boxShadow: '0px 1px 4px rgba(0, 0, 0, 0.3)',
    zIndex: 1000,
});

const ColorBox = styled('div')(({ color }) => ({
    width: '24px',
    height: '24px',
    backgroundColor: color,
}));

const Label = styled('span')({
    marginLeft: '5px',
    fontSize: '12px',
});

const LegendItem = ({ color, range }) => (
    <div style={{ display: 'flex', alignItems: 'center', marginBottom: '5px' }}>
        <ColorBox color={color} />
        <Label>{range}</Label>
    </div>
);

const HexidH3mapLegend = ({ colorMapping }) => (
    <LegendContainer>
         <Typography variant="subtitle1">{colorMapping[0]}</Typography>
        {colorMapping.slice(1).map(({ color, range }) => (
            <LegendItem key={range} color={color} range={range} />
        ))}
    </LegendContainer>
);

export default HexidH3mapLegend;