# Use an official Node.js runtime as a parent image (version 18)
FROM node:20

# Set the working directory in the container
WORKDIR /app

# Copy the frontend application directory contents into the container at /usr/src/app
COPY . .

# Install any needed packages specified in package.json
# Note: The base image already includes Node.js and npm, so we don't need to install them separately.
RUN npm install

# Run npm run dev when the container launches
CMD ["npm", "run", "dev"]