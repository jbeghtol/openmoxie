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
* STT and chat inferences are serviced through OpenAI.  You must export a valid OPENAI_API_KEY into your environment before running

# Running your own - DOCKER edition

1. Clone project
2. Install docker
3. run `docker-compose up --build -d`
4. Visit http://localhost:8001/hive
5. Depending on your PC firewall, expose port 8883

# Running your own instance

1. Clone project
2. Install dependencies
```
python3 -m pip install -r requirements.txt
```
3. Make initial migrations
```
python3 site/manage.py makemigrations
```
4. Run initial migration
```
python3 site/manage.py migrate
```
5. Create a superuser 
```
python site/manage.py createsuperuser
```
6. Run the initial data import
```
python3 site/manage.py init_data
```
7. Edit `site\openmoxie\settings.py` and edit this block with your own MQTT host
```
MQTT_ENDPOINT = {
    'host': 'HOSTHERE',
    'port': 8883,
    'project': 'openmoxie',
    'cert_required': True,
}
```
8. Run the service (Note: no-reload is currently required to prevent the mqtt supervisor from being created twice for some reason.)
```
cd site
python3 manage.py runserver --noreload
```

Once it is running, you may visit http://localhost:8000/hive for the dashboard.

# MQTT Broker

I have been running this all from a headless Ubuntu system using mosquitto MQTT as a broker and configured it for anonymous
access, which is generally a bad idea when the services are running with payment attached.  But I wanted to share my setup
in case anyone wanted to replicate it as a starting point on their own system.

```
sudo apt-get install mosquitto
```

My site configuration for mosquitto in `/etc/mosquitto/conf.d/openmoxie.conf`
```
listener 8883
cafile /etc/letsencrypt/live/duranaki.com/chain.pem
keyfile /etc/letsencrypt/live/duranaki.com/privkey.pem
certfile /etc/letsencrypt/live/duranaki.com/cert.pem
allow_anonymous true
```

I'm using Let's Encrypt with my apache instance, and have allowed ACL permission for mosquitto to read them for it's SSL connections and
will be using a virtual host proxy to route openmoxie subdomain to the django port, so all external webtraffic is nicely encrypted.  The
config for reference.

```
<IfModule mod_ssl.c>
<VirtualHost *:443>
        ServerAdmin webmaster@localhost
        ServerName openmoxie.duranaki.com

        ErrorLog ${APACHE_LOG_DIR}/openmoxie_error.log
        CustomLog ${APACHE_LOG_DIR}/openmoxie_access.log combined
        SSLEngine on
        ProxyRequests Off
        ProxyPreserveHost On
        ProxyPass / http://localhost:8000/
        ProxyPassReverse / http://localhost:8000/

Include /etc/letsencrypt/options-ssl-apache.conf
SSLCertificateFile /etc/letsencrypt/live/duranaki.com/fullchain.pem
SSLCertificateKeyFile /etc/letsencrypt/live/duranaki.com/privkey.pem
</VirtualHost>
</IfModule>
```
