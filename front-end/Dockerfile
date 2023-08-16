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