# Open Moxie

This project is part of a simpler infrastructure replacement for Moxie cloud services.
It is currently a pure python project that performs the service logic over MQTT to
Moxie.  It relies on an mqtt broker, and connects as a supervisor client to that broker
to provide the key services to make Moxie operational.

## Components

Currently this project contains the following:

* Django app for basic web services and database (using sqlite3 bindings)
* pymqtt based service code to handle device
* A simple MQTT based STT provider using OpenAI Whisper
* A simple MQTT based remote chat service using single prompt inferences from OpenAI

## Dependencies

* This project needs an external MQTT broker.  This is currently based on mosquitto MQTT service.

# Running your own instance

1. Clone project
2. Install dependencies via `python3 -m pip install -r requirements.txt`
3. Make initial migrations `cd site; python3 manage.py makemigrations`
4. Run initial migration `cd site; python3 manage.py migrate`
5. Create a superuser `cd site; python manage.py createsuperuser`
6. Run the initial data import `cd site; python3 manage.py init_data`
7. Edit `site\openmoxie\settings.py` and edit this block with your own MQTT host
```
MQTT_ENDPOINT = {
    'host': 'duranaki.com',
    'port': 8883,
    'project': 'openmoxie',
    'cert_required': True,
}
```
8. Run the service `cd site; python3 manage.py runserver --noreload` (Note: no-reload is currently required to prevent the mqtt supervisor from being created twice for some reason.)

Once it is running, you may visit http://localhost:8000/hive for the dashboard.


