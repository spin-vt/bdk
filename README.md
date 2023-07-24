# bdk
Tool developed by the SPIN Lab at Virginia Tech. This branch is dedicated to build and use the app with docker
This branch is for deploying the container published on dockerhub to your server

# Environment variable and image name
1) You should also change the image name in docker-compose.yml for backend, worker, frontend. The format is {dockeraccountusername}/backend:latest for backend. This ensure when executing docker-compose pull the built image on your dockerhub account will be pulled to the server. <br>
2) You will also need a .env file formatted as below. <br>
POSTGRES_USER={Fill here} <br>
POSTGRES_PASSWORD={Fill here} <br>
POSTGRES_DB={Fill here}<br>
POSTGRES_HOST_AUTH_METHOD=trust<br>
DB_HOST=db<br>
DB_PORT=5432<br>
SECRET_KEY={Fill here}<br>
JWT_SECRET={Fill here}<br>

# Building and running the docker container
To build and run the docker container on your container, simply goes to the "bdk" folder, checkout to this branch, and run the following commands
1) `docker-compose pull`
2) `docker-compose up`

# Database migration synchonization
Database migration, managed by a tool call alembic, is only effective when postgres database is set up. On the first "docker-compose up" run the database might not be setup while migration command is issued, causing an no-op for database migration. You can verify if migration is successful by trying to register an account as shown in the picture below. You should be redirected to the homepage when you click on the "register" button after you put in your username and password. If not, You could simply stop the container, rerun the container with command `docker-compose up`, which should fix the issue.
![Web capture_11-7-2023_225525_localhost](https://github.com/spin-vt/bdk/assets/36636157/ee39f6f8-7bc6-4a21-9d78-40dee3c2f706)

