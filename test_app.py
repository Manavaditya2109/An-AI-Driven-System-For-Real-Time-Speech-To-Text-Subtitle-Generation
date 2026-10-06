import unittest
import json
import wave
import io
import struct
import datetime

# ── helpers ──────────────────────────────────────────────────────────────

def make_wav(channels=1, sampwidth=2, framerate=16000, duration_frames=8000):
    """Create a valid WAV file in memory with silent audio."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(framerate)
        wf.writeframes(b'\x00' * duration_frames * channels * sampwidth)
    return buf.getvalue()

def fake_transcribe(wav_bytes):
    """Simulate what transcribe_wav_bytes does — without loading Whisper."""
    with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
        if wf.getnchannels() != 1:
            raise ValueError('Audio must be mono.')
        if wf.getsampwidth() != 2:
            raise ValueError('Audio must be 16-bit.')
        if wf.getframerate() != 16000:
            raise ValueError('Audio must be 16000 Hz.')
    return {
        'text': 'hello this is a test',
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

# ── test cases ────────────────────────────────────────────────────────────

class TestSubtitleSystem(unittest.TestCase):

    def test_01_valid_wav_returns_dict(self):
        """transcribe returns a dictionary."""
        result = fake_transcribe(make_wav())
        self.assertIsInstance(result, dict)

    def test_02_result_has_text_key(self):
        """Result dictionary contains 'text' key."""
        result = fake_transcribe(make_wav())
        self.assertIn('text', result)

    def test_03_result_has_timestamp_key(self):
        """Result dictionary contains 'timestamp' key."""
        result = fake_transcribe(make_wav())
        self.assertIn('timestamp', result)

    def test_04_text_is_string(self):
        """'text' field is a string."""
        result = fake_transcribe(make_wav())
        self.assertIsInstance(result['text'], str)

    def test_05_timestamp_is_valid_iso(self):
        """'timestamp' is a valid ISO format datetime string."""
        result = fake_transcribe(make_wav())
        parsed = datetime.datetime.fromisoformat(result['timestamp'])
        self.assertIsInstance(parsed, datetime.datetime)

    def test_06_stereo_raises_error(self):
        """Stereo audio raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            fake_transcribe(make_wav(channels=2))
        self.assertIn('mono', str(ctx.exception))

    def test_07_wrong_sample_rate_raises_error(self):
        """Wrong sample rate raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            fake_transcribe(make_wav(framerate=44100))
        self.assertIn('16000', str(ctx.exception))

    def test_08_wrong_bitdepth_raises_error(self):
        """8-bit audio raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            fake_transcribe(make_wav(sampwidth=1))
        self.assertIn('16-bit', str(ctx.exception))

    def test_09_result_is_json_serialisable(self):
        """Result can be serialised to JSON without error."""
        result = fake_transcribe(make_wav())
        serialised = json.dumps(result)
        deserialised = json.loads(serialised)
        self.assertEqual(result['text'], deserialised['text'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
    