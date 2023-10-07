FROM alpine:3.17

WORKDIR /app

# Install system packages and Node.js
RUN apk update && \
    apk add --no-cache git \
    build-base \
    sqlite-dev \
    zlib-dev \
    bash \
    nodejs \
    npm

# Verify installation
RUN echo "Node version:" \
  && node --version \
  && echo "npm version:" \
  && npm --version

# Install application packages
COPY package*.json ./
RUN npm install

COPY . .

CMD ["npm", "run", "dev"]

# RUN npm install --only=production

# # Copy the rest of the application files
# COPY . .

# # Build the Next.js app for production
# RUN npm run build

# # Command to start the production server
# CMD ["npm", "run", "start"]
