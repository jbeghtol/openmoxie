# Pin so broker log phrasing (connect/disconnect) doesn't drift under :latest.
# Hub tags for 2.1.x use the -alpine suffix (2.1.2 alone is not published).
FROM eclipse-mosquitto:2.1.2-alpine

# Copy in the pre-generated keys
COPY ./keys /mosquitto/config/keys

# Copy config from openmoxie
COPY ./site/data/openmoxie.conf /mosquitto/config/mosquitto.conf

CMD ["mosquitto", "-c", "/mosquitto/config/mosquitto.conf"]