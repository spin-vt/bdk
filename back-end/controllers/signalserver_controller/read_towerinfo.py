import csv
from io import StringIO

def read_tower_csv(csv_file):
    content = StringIO(csv_file.stream.read().decode("UTF8"), newline=None)
    csv_reader = csv.DictReader(content)
    
    # Initialize an empty list to store all tower data
    towers_data = []

    # Iterate over each row in the CSV and append the tower data to the list
    for row in csv_reader:
        try:
            tower_info = {
                'towerName': row['Tower Name'],
                'latitude': float(row['Latitude(degrees)']),
                'longitude': float(row['Longitude(degrees)']),
                'frequency': float(row['Frequency(MHz)']),
                'coverageRadius': float(row['Coverage Radius(Km)']),
                'antennaHeight': float(row['Antenna Height(meters)']),
                'antennaTilt': float(row['Antenna Tilt(degrees)']),
                'horizontalFacing': float(row['Horizontal Facing(degrees)']),
                'floorLossRate': int(row['Floor Loss Rate(dB)']),
                'effectiveRadPower': float(row['Effective Radiated Power(dBd)']),
                'downtilt': float(row['Downtilt(degrees)']),
                'downtiltDirection': float(row['Direction(degrees)'])

            }
            towers_data.append(tower_info)
        except ValueError as e:
            # Log the exception e
            # Return or handle the error for the particular row
            continue  # or you can use 'break' to stop the loop if the error is critical

    # After the loop, return the list of towers data
    return towers_data
