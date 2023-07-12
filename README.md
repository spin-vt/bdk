# bdk
Tool developed by the SPIN Lab at Virginia Tech. This branch is dedicated to build and use the app with docker

# Line-ending on Windows
This app run necessary shell scripts written in unix-style line-ending(LF). If you are building your container in Windows, you can use the following command to change your git global setting to ensure LF line-ending when you clone the repo. 
1) `git config --global core.autocrlf false`
2) `git config --global core.eol lf`

# Building and running the docker container
To build and run the docker container, simply goes to the "bdk" folder and run the following commands
1) `docker-compose build`
2) `docker-compose up`

# Database migration synchonization
Database migration, managed by a tool call alembic, can only be effective when postgres database had set up. On the first run the database might takes some time to setup while migration is taking place, causing an no-op for database migration. You can verify if migration is successful by trying to register an account, if you didn't get redirect to homepage. You could simply stop and rerun your container, which should fix the issue.

# Additional notes
You need to login before you upload your files for processing, even though we are not displaying error message in the UI right now. We are working on updating the user interface to remind user of this policy. 
