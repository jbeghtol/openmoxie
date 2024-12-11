from time import sleep
from django.core.management.commands.runserver import Command as RunserverCommand
from django.core.management import call_command
from django.conf import settings
import threading
from hive.mqtt.moxie_server import create_service_instance, cleanup_instance

class Command(RunserverCommand):
    _run_enabled = True
    def handle(self, *args, **options):
        thread = threading.Thread(target=self.deamon_worker)
        thread.daemon = True  # Set as daemon thread so it exits when main thread exits
        thread.start()

        # Call the base handle method to start the development server
        super().handle(*args, **options)

    def deamon_worker(self):
        self._run_enabled = True
        print('Starting MQTT Services...')
        from hive.mqtt.moxie_server import create_service_instance
        ep = settings.MQTT_ENDPOINT
        instance = create_service_instance(project_id=ep['project'], host=ep['host'], port=ep['port'], cert_required=ep.get('cert_required', True))
        while self._run_enabled:
            sleep(60)
            instance.print_metrics()
