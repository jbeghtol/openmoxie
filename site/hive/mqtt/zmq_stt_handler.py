from .moxie_zmq_handler import ZMQHandler
from .protos.embodied.perception.audio.zmqSTT_pb2 import zmqSTTRequest,zmqSTTResponse
import soundfile as sf
import numpy as np
import io
import time
import logging
import concurrent.futures
from .ai_factory import create_openai

LOG_WAV=False
OPENAI_MODEL='whisper-1'

logger = logging.getLogger(__name__)

def now_ms():
    return time.time_ns() // 1_000_000


'''
An STT Session is a stream of contiguous audio coming out of the Robot's voice activity detector (VAD). This
is a very simple implementation tuned to OpenAI Whisper.  Their API doesn't support streaming, so we simply
accumulate the audio frames, then transcribe them when complete.
'''
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
        return len(self._stream_bytes)
    
    def perform(self):
        logger.info(f'Processing session_id {self._session_id} with {len(self._stream_bytes)} bytes')
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
            client = create_openai()
            transcript = client.audio.transcriptions.create(
                file=('test.wav', wav_bytes),
                model=OPENAI_MODEL,
                response_format="verbose_json",
                timestamp_granularities=["word"])
            resp.speech = transcript.text
            min_start = min(d.start for d in transcript.words) if transcript.words else 0
            max_end = max(d.end for d in transcript.words) if transcript.words else 0
            resp.start_timestamp = self._start_ts + int(min_start*1000)
            resp.end_timestamp = self._start_ts + int(max_end*1000)
            logger.info(f'STT-FINAL: {transcript.text}')
        except Exception as e:
            logger.warning(f'Exception handling openAI request: {e}')
            resp.error_code = 66
            resp.error_message = str(e)

        # send response to device
        self._parent.zmq_reply(self._device_id, resp)

        if LOG_WAV:
            logfile = f'{self._session_id}.wav'
            with open(logfile, 'wb') as f:
                f.write(wav_bytes)
                logger.info(f'Wrote WAV data to {logfile}')

'''
This is the handler for all Speech data packets.  By default, the Robot uses stt:4, which begins sending
audio data during session to be transcribed.  If Robot is using stt:0, no STT packets will arrive here.
This is also very simple.  We create unique sessions for each device_id / session pair, pass them all the
data inline, and when a session hits end-of-speech, queue transcription to run in the background.
'''
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
        total_sess_bytes = self._sessions[sesskey].on_request(req)
        # every time we reach EOS, we background it for work
        logger.debug(f'ZMQ Speech VAD: {req.vad} TotalBytes: {total_sess_bytes}')
        if req.vad == req.VADState.END_OF_SPEECH:
            logger.info(f'Session reached END OF SPEECH')
            # session is done, do the work
            sess = self._sessions.pop(sesskey)
            self._worker_queue.submit(sess.perform)
