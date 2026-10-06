import os, json, wave, tempfile, subprocess, io, datetime
from faster_whisper import WhisperModel
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

load_dotenv()

SAMPLE_RATE = 16000
WHISPER_MODEL_SIZE = os.environ.get('WHISPER_MODEL_SIZE', 'small')

app      = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')

_model = None

def get_model():
    global _model
    if _model is None:
        print(f"[*] Loading Whisper model '{WHISPER_MODEL_SIZE}'...")
        _model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
        print("[*] Model loaded.")
    return _model

def convert_to_wav_16k(input_bytes):
    with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp_in:
        tmp_in.write(input_bytes)
        in_path = tmp_in.name
    out_path = in_path.replace('.webm', '.wav')
    try:
        subprocess.run(
            ['ffmpeg', '-y', '-i', in_path,
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
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name
    try:
        model = get_model()
        segments, _ = model.transcribe(tmp_path, language='en', beam_size=5)
        seg_list = list(segments)
        text = ' '.join([seg.text.strip() for seg in seg_list]).strip()
        if seg_list:
            avg_confidence = sum([seg.avg_logprob for seg in seg_list]) / len(seg_list)
            # Convert log probability to 0-1 scale
            confidence = min(1.0, max(0.0, (avg_confidence + 1.0)))
        else:
            confidence = 0.0
        return {
            'text':       text,
            'confidence': round(confidence, 2),
            'timestamp':  datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
    finally:
        if os.path.exists(tmp_path): os.unlink(tmp_path)

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