# Pull official base image
FROM node:16

# Set work directory in the Docker image
WORKDIR /app

# Copy package.json and package-lock.json (if available)
COPY package*.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy the rest of the application
COPY . .

# Expose port and define CMD
EXPOSE 3000
CMD ["npm", "run", "dev"]
