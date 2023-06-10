# Use a base image with Node.js pre-installed
FROM node:14

# Set the working directory inside the container
WORKDIR /app

# Copy the application code
COPY . .

# Expose the port on which the application will run
EXPOSE 3000

# Specify the command to start the application
CMD ["npm", "run", "dev"]
