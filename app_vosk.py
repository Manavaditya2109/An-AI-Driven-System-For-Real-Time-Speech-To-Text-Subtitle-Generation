import os, json, wave, tempfile, subprocess, io, datetime
from vosk import Model, KaldiRecognizer
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

load_dotenv()

MODEL_PATH  = os.environ.get('VOSK_MODEL_PATH', 'vosk-model-en-in-0.5')
SAMPLE_RATE = 16000
CHUNK_SIZE  = 4000

app      = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')

_model = None

def get_model():
    global _model
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Vosk model not found at '{MODEL_PATH}'.")
        _model = Model(MODEL_PATH)
    return _model

def convert_to_wav_16k(input_bytes):
    with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp_in:
        tmp_in.write(input_bytes)
        in_path = tmp_in.name
    out_path = in_path.replace('.webm', '.wav')
    try:
        subprocess.run(
            ['ffmpeg', '-y', '-i', in_path,
 '-af', 'highpass=f=200,lowpass=f=3000,afftdn=nf=-25',
 '-ar', str(SAMPLE_RATE), '-ac', '1',
 '-sample_fmt', 's16', '-f', 'wav', out_path],
            capture_output=True, check=True
        )
        with open(out_path, 'rb') as f:
            return f.read()
    finally:
        if os.path.exists(in_path):  os.unlink(in_path)
        if os.path.exists(out_path): os.unlink(out_path)

def transcribe_wav_bytes(wav_bytes):
    recognizer = KaldiRecognizer(get_model(), SAMPLE_RATE)
    segments   = []
    with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
        if wf.getnchannels() != 1:
            raise ValueError('Audio must be mono.')
        if wf.getsampwidth() != 2:
            raise ValueError('Audio must be 16-bit.')
        if wf.getframerate() != SAMPLE_RATE:
            raise ValueError(f'Audio must be {SAMPLE_RATE} Hz.')
        while True:
            data = wf.readframes(CHUNK_SIZE)
            if len(data) == 0: break
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text   = result.get('text', '').strip()
                if text: segments.append(text)
    final = json.loads(recognizer.FinalResult())
    final_text = final.get('text', '').strip()
    if final_text: segments.append(final_text)
    return {
        'text':      ' '.join(segments),
        'segments':  segments,
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def on_connect():
    print(f'[+] Client connected: {request.sid}')

@socketio.on('disconnect')
def on_disconnect():
    print(f'[-] Client disconnected: {request.sid}')

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    try:
        raw = bytes(data)
        if len(raw) < 5000:
            return
        wav_bytes = convert_to_wav_16k(raw)
        result    = transcribe_wav_bytes(wav_bytes)
        if result['text']:
            emit('subtitle', result)
    except subprocess.CalledProcessError as exc:
        emit('error', {'message': f'ffmpeg error: {exc.stderr.decode(errors="replace")}'})
    except Exception as exc:
        emit('error', {'message': str(exc)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)