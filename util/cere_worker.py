import json
import base64
import os
import time
import threading
from datetime import datetime, timedelta, timezone
from subprocess import Popen, PIPE, STDOUT

class CereWorker:

    _tts_app : any
    _playback_app : any
    _tts_proc : any

    def __init__(self, tts_app, playback_app):
        self._tts_app = tts_app
        self._playback_app = playback_app
        self._tts_proc = None

    def start(self):
        print(f"Spawning {self._tts_app}...")
        self._tts_proc = Popen([self._tts_app], stdout=PIPE, stdin=PIPE, stderr=PIPE)
        self._read_thread = threading.Thread(target=self.read_cere_out, args=("Cereproc Output Reader",))
        self._read_thread.start()

    def stop(self):
        self._tts_proc.kill()

    def queue_markup(self, markup_string):
        self._tts_proc.stdin.write(f"{markup_string}\n".encode())
        self._tts_proc.stdin.flush()

    def read_cere_out(self, name):
        while self._tts_proc.poll() is None:
            line = self._tts_proc.stdout.readline().decode()
            if "audio to:" in line:
                wav = line.split(":")[1].strip()
                Popen([self._playback_app,wav])

#cw = CereWorker("./generate_tts")
#cw.start()
#time.sleep(1.0)
#cw.queue_markup("This is a test")
#time.sleep(5.0)