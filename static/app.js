const socket      = io();
const startBtn    = document.getElementById('startBtn');
const stopBtn     = document.getElementById('stopBtn');
const downloadBtn = document.getElementById('downloadBtn');
const status      = document.getElementById('status');
const overlay     = document.getElementById('subtitleOverlay');
const transcript  = document.getElementById('transcript');

let mediaRecorder, stream;

startBtn.addEventListener('click', async () => {
  try {
    stream        = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });

    mediaRecorder.ondataavailable = async (event) => {
      if (event.data && event.data.size > 0) {
        const buf = await event.data.arrayBuffer();
        socket.emit('audio_chunk', buf);
      }
    };

    mediaRecorder.start(5000

    );
    startBtn.disabled = true;
    stopBtn.disabled  = false;
    status.textContent = 'Recording...';

  } catch (err) {
    alert('Microphone error: ' + err.message);
  }
});

stopBtn.addEventListener('click', () => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
    stream.getTracks().forEach(t => t.stop());
    startBtn.disabled = false;
    stopBtn.disabled  = true;
    status.textContent = 'Stopped.';
  }
});

socket.on('subtitle', (data) => {
  const conf = data.confidence || 0;
  const color = conf > 0.7 ? '#2ecc71' : conf > 0.4 ? '#f39c12' : '#e74c3c';
  const label = conf > 0.7 ? 'High' : conf > 0.4 ? 'Medium' : 'Low';

  const seg = document.createElement('p');
  seg.innerHTML = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${color};margin-right:8px;"></span>${data.text} <small style="color:${color}">[${label}]</small>`;
  overlay.appendChild(seg);
  seg.scrollIntoView({ behavior: 'smooth' });

  const ts = new Date(data.timestamp).toLocaleTimeString();
  transcript.value += `[${ts}][${label}] ${data.text}\n`;
  transcript.scrollTop = transcript.scrollHeight;
});

socket.on('error', (data) => {
  console.log('Audio chunk error (ignored):', data.message);
});

socket.on('connect',    () => { status.textContent = 'Connected.'; });
socket.on('disconnect', () => { status.textContent = 'Disconnected. Retrying...'; });

downloadBtn.addEventListener('click', () => {
  const text = transcript.value;
  if (!text.trim()) { alert('No transcript to download yet.'); return; }
  const blob = new Blob([text], { type: 'text/plain' });
  const url  = URL.createObjectURL(blob);
  const a    = Object.assign(document.createElement('a'), { href: url, download: 'transcript.txt' });
  a.click();
  URL.revokeObjectURL(url);
});