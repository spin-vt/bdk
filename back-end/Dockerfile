# Use a base image with Python and Redis pre-installed
FROM python:3.9

# Set the working directory inside the container
WORKDIR /app

# Copy the application code (if applicable)
COPY . .

# Expose the port on which the application will run
EXPOSE 8000
EXPOSE 5432

# Specify the command to start the application
CMD ["/bin/bash", "-c", "source env/bin/activate && celery -A routes.celery worker --loglevel=DEBUG & python routes.py"]

# Install the Python dependencies using pip
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install psycopg2-binary
RUN pip install shapely
RUN pip install numpy
RUN pip install pandas
RUN pip install fiona
RUN pip install pyproj
RUN pip install geopandas

