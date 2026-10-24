"""Offline STT tests; no Django setup, MQTT broker or API credentials needed.

Run from the site directory:
    python -m unittest hive.test_stt -v
"""
import concurrent.futures
import io
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import soundfile as sf
from openai.types.audio.transcription_verbose import TranscriptionVerbose

from hive.mqtt.zmq_stt_handler import STTHandler, STTSession
from hive.mqtt.protos.embodied.perception.audio.zmqSTT_pb2 import (
    zmqSTTRequest,
    zmqSTTResponse,
)


class STTTests(unittest.TestCase):
    def setUp(self):
        self.server = Mock()
        self.handler = STTHandler(self.server)
        self.addCleanup(self.handler._worker_queue.shutdown)
        factory_patch = patch("hive.mqtt.zmq_stt_handler.create_openai")
        self.factory = factory_patch.start()
        self.addCleanup(factory_patch.stop)
        self.api = self.factory.return_value.audio.transcriptions.create

    def transcribe(self, transcript=None, error=None):
        self.api.return_value = transcript
        self.api.side_effect = error
        session = STTSession(self.handler, "robot", "utterance")
        session.on_request(zmqSTTRequest(
            timestamp=10000,
            audio_content=b"\x00\x00" * 16000,
            uuid="utterance",
        ))
        session.perform()
        self.server.send_zmq_to_bot.assert_called_once()
        device, response = self.server.send_zmq_to_bot.call_args.args
        self.assertEqual(device, "robot")
        self.assertEqual(response.uuid, "utterance")
        self.assertEqual(response.type, zmqSTTResponse.FINAL)
        # Exercise protobuf serialization as well as field assignments.
        return zmqSTTResponse.FromString(response.SerializeToString())

    def test_segment_boundaries_and_wav_payload(self):
        # Parse the actual SDK response schema, with no word timestamps.
        transcript = TranscriptionVerbose.model_validate({
            "text": "hello there", "duration": 1.0, "language": "english",
            "segments": [
                {"id": i, "seek": 0, "start": start, "end": end,
                 "text": text, "tokens": [], "temperature": 0,
                 "avg_logprob": 0, "compression_ratio": 1, "no_speech_prob": 0}
                for i, (start, end, text) in enumerate([
                    (0.7, 0.9, "there"), (0.2, 0.6, "hello"),
                ])
            ],
        })
        response = self.transcribe(transcript)
        self.assertEqual(response.speech, "hello there")
        self.assertEqual(response.start_timestamp, 10200)
        self.assertEqual(response.end_timestamp, 10900)
        self.assertEqual(response.error_code, 0)
        args = self.api.call_args.kwargs
        self.assertEqual(args["model"], "whisper-1")
        self.assertEqual(args["response_format"], "verbose_json")
        self.assertEqual(args["timestamp_granularities"], ["segment"])
        audio = sf.info(io.BytesIO(args["file"][1]))
        self.assertEqual((audio.samplerate, audio.channels, audio.frames),
                         (16000, 1, 16000))
        self.assertEqual(audio.subtype, "PCM_16")

    def test_empty_transcription(self):
        response = self.transcribe(SimpleNamespace(text="", segments=[]))
        self.assertEqual(response.speech, "")
        self.assertEqual((response.start_timestamp, response.end_timestamp),
                         (10000, 10000))
        self.assertEqual(response.error_code, 0)

    def test_optional_segments_are_none(self):
        response = self.transcribe(SimpleNamespace(text="", segments=None))
        self.assertEqual(response.error_code, 0)
        self.assertEqual(response.end_timestamp, 10000)

    def test_api_failure_still_sends_error_response(self):
        with self.assertLogs("hive.mqtt.zmq_stt_handler", level="WARNING"):
            response = self.transcribe(error=RuntimeError("synthetic failure"))
        self.assertEqual(response.error_code, 66)
        self.assertEqual(response.error_message, "synthetic failure")

    def test_client_reused_for_successive_phrases(self):
        for _ in range(2):
            self.server.reset_mock()
            self.transcribe(SimpleNamespace(text="hello", segments=[]))
        self.factory.assert_called_once_with()
        self.assertEqual(self.api.call_count, 2)

    def test_each_worker_has_its_own_client(self):
        barrier = threading.Barrier(2)
        self.factory.side_effect = lambda: object()

        def worker():
            first = self.handler.get_stt_client()
            barrier.wait(timeout=5)
            return first, self.handler.get_stt_client()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            pairs = [future.result(timeout=10) for future in futures]
        self.assertIs(pairs[0][0], pairs[0][1])
        self.assertIs(pairs[1][0], pairs[1][1])
        self.assertIsNot(pairs[0][0], pairs[1][0])
        self.assertEqual(self.factory.call_count, 2)


if __name__ == "__main__":
    unittest.main()
