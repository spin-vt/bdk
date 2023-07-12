# BDK
BDK is a tool developed by the SPIN Lab at Virginia Tech.

## Necessary Dependencies
The following dependencies are needed to run BDK:
1. [PostgreSQL](https://www.postgresql.org/download/)
2. [Redis Server](https://redis.io/docs/getting-started/)
3. [Node.js](https://nodejs.org/en/)

## Getting Started

### Setting up Repo Locally

1. Clone the repository to your local machine.
2. There are two folders: "front-end", which houses the frontend code and "back-end" that houses the backend code.
3. `cd` into `back-end`.

### Setting Up Backend

1. You may or may not have a Python environment set up.
2. To check if you have Python, please type: `python3 --version`.
3. To set up a Python virtual environment, type: `python3 -m venv env` for Mac and `py -m venv env` for Windows users (skip to step 8 for WSL environments).
4. For WSL try the following. If you also had problems on Mac or Windows try to replicate the following steps but with syntax for your respective OS. 
    * `sudo apt-get update`
    * `sudo apt-get install python3-pip`
    * `python3 -m pip install --upgrade pip setuptools wheel`
    * `python3 -m pip install virtualenv`
    * `python3 -m virtualenv env` or `python3 -m venv env`
5. To activate the Python environment, type: `source env/bin/activate` for Mac and `.\env\Scripts\activate` for Windows users.
6. You may be missing some dependencies so run the following before the next step: 
    * `sudo apt-get install postgresql postgresql-contrib`
    * `sudo apt-get install libpq-dev`
7. Then, do `pip install -r requirements.txt` to automatically download the used libraries.

### Setting up Database
For this implementation, you need to run the following commands in "bdk/back-end" folder to set up your database:

1. `source env/bin/activate`
2. `alembic revision --autogenerate -m "Initial migration"`
3. `alembic upgrade head`

### Installing Redis 

1. The backend uses Redis as a message broker to communicate with alive Celery workers. This is necessary if you want asynchronous queuing to take place, but at the same time, may be difficult to set up and use entirely.
2. For Mac, make sure you have brew installed. Type `brew --version` to see if you do. Then, type `brew install redis` which will install redis for you.
3. For Windows, you can follow this tutorial: [Redis on Windows](https://developer.redis.com/create/windows/) (I - Rayhan - don't have experience installing Redis on Windows as I have a Mac).

### Setting up Frontend

1. Change your directory to the "front-end" by typing `cd ..` then `cd front-end`.
2. I set up a proxy to our Flask app in the package.json file, which you can edit if you want to change your port, but this proxy should work out of the box (with no changes necessary).
3. Make sure you have npm and node on your local machine.
4. Type in `npm i --force` or `npm install --force` to install all the packages.

## Running the FullStack App 
You need three terminal instances to run this app, here is an example in vscode
![image](https://github.com/spin-vt/bdk/assets/36636157/c8006851-7de8-45d5-a2ab-0f10c5460601)

## Running the Backend 

1. This part of the guide assumes you have Redis and PostgreSQL running on your machine and that you have downloaded all the Python libraries in the requirements.txt file.
2. The first step is making sure you are on the backend directory (back-end).
3. Next, activate the Python virtual environment with `source env/bin/activate`, and type: `celery -A controllers.celery_controller.celery_config.celery worker --loglevel=DEBUG`. ![image](https://github.com/spin-vt/bdk/assets/36636157/668f30fa-119f-41f3-b1cd-9cd935082b59)
4. After, open another terminal in this same working directory "back-end" and activate Python virtual environment with `source env/bin/activate` and type `python3 routes.py`. ![image](https://github.com/spin-vt/bdk/assets/36636157/d0d40927-bc38-4338-9e80-7de22cfcc581)

## Running the Frontend 

1. To run the front-end app, Navigate to directory "front-end" and type `npm run dev`. ![image](https://github.com/spin-vt/bdk/assets/36636157/e5a97387-77f6-4794-822d-852dc47ae5d7)
2. Navigate to "http://localhost:3000" in your browser.
