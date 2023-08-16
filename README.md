# bdk
Tool developed by the SPIN Lab at Virginia Tech. This branch is dedicated to build and use the app with docker

## Necessary Dependencies
The following dependencies are needed to run BDK:
1. [Node.js](https://nodejs.org/en/)

# Line-ending on Windows
This app run necessary shell scripts written in unix-style line-ending(LF). If you are building your container in Windows, you can use the following command to change your git global setting before you clone the repo to ensure LF line-ending. 
1) `git config --global core.autocrlf false`
2) `git config --global core.eol lf`

# Before you start building
Run the following commands in the front-end directory
1) `npm install`
2) `npm run build`

# Building and running the docker container
To build and run the docker container, simply goes to the "bdk" folder and run the following commands
1) `docker-compose build`
2) `docker-compose up`

# Database migration synchonization
Database migration, managed by a tool call alembic, is only effective when postgres database is set up. On the first "docker-compose up" run the database might not be setup while migration command is issued, causing an no-op for database migration. You can verify if migration is successful by trying to register an account as shown in the picture below. You should be redirected to the homepage when you click on the "register" button after you put in your username and password. If not, You could simply stop the container, rerun the container with command `docker-compose up`, which should fix the issue.
![Web capture_11-7-2023_225525_localhost](https://github.com/spin-vt/bdk/assets/36636157/ee39f6f8-7bc6-4a21-9d78-40dee3c2f706)
