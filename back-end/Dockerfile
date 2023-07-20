FROM python:3.9-slim-buster

RUN apt-get update && apt-get install -y \
  gcc \
  python3-dev \
  libpq-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

# # Copy supervisor configuration
# COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

COPY . .

# CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
CMD ["python3", "routes.py"]