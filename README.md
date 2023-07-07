# bdk
Tool developed by the SPIN Lab at Virginia Tech

For this implementation, you need run the following commands in "bdk" folder to set up your database
1) `alembic revision --autogenerate -m "Initial migration"`

2) `alembic upgrade head`

# Necessary dependencies
1) postgresql https://www.postgresql.org/download/
2) redis-server https://redis.io/docs/getting-started/
3) node.js https://nodejs.org/en

# Getting Started
## Setting up Repo Locally
1) Clone the reposistory to your local machine 
2) There are two folders: "front-end", which houses the frontend code and "back-end" that hosues the backend code 
3) cd into back-end
## Setting Up Backend
4) You may or may not have a python environment set up 
5) To check if you have python, please type: "python3 --version"
7) To set up a python virtual env, type:  "python3 -m venv env" for MAC and "py -m venv env" for Windows users
8) To activate the python env, type: "source env/bin/activate" for MAC and ".\env\Scripts\activate" for Windows users
9) Then, do "pip install -r requirements.txt" to automatically download the used libraries 
10) To run the application, you can type "python3 routes.py" into your terminal where your current cwd is back-end 
9) If you want to change the port, you can do so py setting the port number in the "app.run" command 
# Installing Redis 
1) The backend uses Redis as a message broker to communicate with alive Celery workers. This is necessary if you want asynchronous queing to 
take place, but at the same time, may be difficult to set up and use entirely. 
2) For Mac, make sure you have brew installed. Type "brew --version" to see if you do. Then, type "brew install redis" which will install redis for you 
3) For Windows, you can follow this tutorial: https://developer.redis.com/create/windows/ (I - Rayhan - don't have experience installing Redis on Windows as I have a Mac) 
## Setting up Frontend
10) change your directory to the "front-end" by typing "cd .." then "cd front-end" 
11) I set up a proxy to our Flask app in the package.json file, which you can edit if you want to change your port, but this proxy should work out of the box (with no changes necessary) 
12) Make sure you have npm and node on your local machine 
13) Type in "npm i --force" or "npm install --force" to install all the packages. 

## Running the FullStack App 
You need three terminal instances to run this app, here is an example in vscode
![image](https://github.com/spin-vt/bdk/assets/36636157/c8006851-7de8-45d5-a2ab-0f10c5460601)

# Running the backend 
1) This part of the guide assumes you have Redis and postgressql running on your machine and that you have downloaded all the python libraries in the requirements.txt file. 
2) The first step is making sure you are on the backend directory (back-end). 
3) Next, "back-end" and activate python virutal environement with "source env/bin/activate", and type: "celery -A routes.celery worker --loglevel=DEBUG". ![image](https://github.com/spin-vt/bdk/assets/36636157/3eb944d8-d7ad-4d7b-b634-d993e591465d)

4) After, open another terminal in this same working directory "back-end" and activate python virutal environement with "source env/bin/activate" type "python3 routes.py". ![image](https://github.com/spin-vt/bdk/assets/36636157/d0d40927-bc38-4338-9e80-7de22cfcc581)

# Running the frontend 
1) To run the front-end app, Navigate to directory "front-end" and type "npm run dev" ![image](https://github.com/spin-vt/bdk/assets/36636157/e5a97387-77f6-4794-822d-852dc47ae5d7)

2) Navigate to "http://localhost:3000" in your browser.


