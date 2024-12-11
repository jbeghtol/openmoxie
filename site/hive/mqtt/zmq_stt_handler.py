from .moxie_zmq_handler import ZMQHandler
from .protos.embodied.perception.audio.zmqSTT_pb2 import zmqSTTRequest,zmqSTTResponse
import soundfile as sf
import numpy as np
import io
import time
import concurrent.futures
from openai import OpenAI

LOG_WAV=False
OPENAI_MODEL='whisper-1'

def now_ms():
    return time.time_ns() // 1_000_000

class STTSession:
    def __init__(self, parent, device_id, session_id):
        self._parent = parent
        self._device_id = device_id
        self._session_id = session_id
        self._stream_bytes = bytearray()
        self._start_ts = None
    def on_request(self, req):
        # future ref, this is technically wrong in the design, this ts is realtime on robot, not audio timestamp
        if not self._start_ts:
            self._start_ts = req.timestamp
        self._stream_bytes += req.audio_content
    def perform(self):
        print(f'Processing session_id {self._session_id} with {len(self._stream_bytes)} bytes')
        buffer = io.BytesIO()
        sf.write(
            buffer,  # File-like object (None for bytes)
            np.frombuffer(self._stream_bytes, dtype=np.int16),
            16000,
            format='WAV',
            subtype='PCM_16'  # 16-bit PCM
            )
        wav_bytes = buffer.getvalue()
        # Create proto response, send regardless
        resp = zmqSTTResponse()
        resp.uuid = self._session_id
        resp.type = resp.ResponseType.FINAL
        resp.timestamp = now_ms()

        try:
            client = OpenAI()
            transcript = client.audio.transcriptions.create(
                file=('test.wav', wav_bytes),
                model=OPENAI_MODEL,
                response_format="verbose_json",
                timestamp_granularities=["word"])
            resp.speech = transcript.text
            min_start = min(d.start for d in transcript.words)
            max_end = max(d.end for d in transcript.words)
            resp.start_timestamp = self._start_ts + int(min_start*1000)
            resp.end_timestamp = self._start_ts + int(max_end*1000)
            print(f'STT-FINAL: {transcript.text}')
        except Exception as e:
            print(f'Exception handling openAI request: {e}')
            resp.error_code = 66
            resp.error_message = str(e)

        # send response to device
        self._parent.zmq_reply(self._device_id, resp)

        if LOG_WAV:
            logfile = f'{self._session_id}.wav'
            with open(logfile, 'wb') as f:
                f.write(wav_bytes)
                print(f'Wrote WAV data to {logfile}')

class STTHandler(ZMQHandler):

    def __init__(self, server):
        super().__init__(server)
        self._sessions = {}
        self._worker_queue = concurrent.futures.ThreadPoolExecutor(max_workers=5)

    def handle_zmq(self, device_id, protoname, protodata):
        req = zmqSTTRequest()
        req.ParseFromString(protodata)
        sesskey = ( device_id, req.uuid )
        if sesskey not in self._sessions:
            self._sessions[sesskey] = STTSession(self, sesskey[0], sesskey[1])
        self._sessions[sesskey].on_request(req)
        # every time we reach EOS, we background it for work
        print(f'VAD State {req.vad}')
        if req.vad == req.VADState.END_OF_SPEECH:
            print(f'Session reached END OF SPEECH')
            # session is done, do the work
            sess = self._sessions.pop(sesskey)
            self._worker_queue.submit(sess.perform)
