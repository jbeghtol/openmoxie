FROM eclipse-mosquitto:latest

# Copy in the pre-generated keys
COPY ./keys /mosquitto/config/keys

# Copy config from openmoxie
COPY ./site/data/openmoxie.conf /mosquitto/config/mosquitto.conf

CMD ["mosquitto", "-c", "/mosquitto/config/mosquitto.conf"]