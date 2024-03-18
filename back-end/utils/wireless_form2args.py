wireless_formfield2args = {
    'latitude': '-lat',
    'longitude': '-lon',
    'frequency': '-f',
    'radius': '-R',
    'antennaHeight': '-txh',
    'antennaTilt': '-dt',
    'horizontalFacing': '-rot',
    'effectiveRadPower': '-erp',
    'downtilt': '-dt',
    'downtiltDirection': '-dtdir'
    # ... additional mappings
    # for th rest below, on the front end
    # these can be buttons that select the options
    
}

wireless_raster_file_format = ['.kmz', '.lcf', '.png', '.ppm']
wireless_vector_file_format = ['.kml', '.png', '.tif']

# runsig.sh -sdf /app/DEM/one_arc_second -erp 1000.0 -lat 46.37980555555556 -lon -116.14330555555556 -f 5785 -txh 54.8 -rot 330 -dt 2 -dtdir 100 -R 10 -pm 1 -res 3600 -o output | genkmz.sh