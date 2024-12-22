## Moxie needs MQTT and services running on MQTT
# Use an official Python base image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install Mosquitto MQTT service and other dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Create a volume for persistent data
VOLUME /app/site/work

# Expose the Mosquitto MQTT port and Django development server port
EXPOSE 8001

ENV DJANGO_SUPERUSER_USERNAME=admin
ENV DJANGO_SUPERUSER_PASSWORD=moxie4ever
ENV DJANGO_SUPERUSER_EMAIL=admin@example.com

# Run Django development server
# - Does data migrations and ensure stock data available, then runs the service
CMD ["bash", "-c", "python3 site/manage.py makemigrations && python3 site/manage.py migrate && python3 site/manage.py init_data && python3 site/manage.py runserver --noreload"]
