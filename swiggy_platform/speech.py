"""Short female narration, with a self-hosted neural fallback and no extra API key."""
from functools import lru_cache
import io
from pathlib import Path
import tempfile
import threading
import time
import wave

_engine = None
_engine_lock = threading.Lock()
_groq_blocked_until = 0.0
ASSETS = {
    "kokoro-v1.0.int8.onnx": 92361271,
    "voices-v1.0.bin": 28214398,
}
ASSET_ROOT = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"


def _asset(name):
    import httpx
    directory = Path(tempfile.gettempdir()) / "swiggy_natural_voice"
    directory.mkdir(exist_ok=True)
    destination = directory / name
    if destination.exists() and destination.stat().st_size == ASSETS[name]:
        return destination
    temporary = directory / (name + ".download")
    try:
        with httpx.stream("GET", ASSET_ROOT + name, follow_redirects=True, timeout=90) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_bytes():
                    output.write(chunk)
        if temporary.stat().st_size != ASSETS[name]:
            raise ValueError("Incomplete natural voice model download")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _kokoro():
    global _engine
    with _engine_lock:
        if _engine is None:
            import onnxruntime
            from kokoro_onnx import Kokoro
            model = _asset("kokoro-v1.0.int8.onnx")
            voices = _asset("voices-v1.0.bin")
            options = onnxruntime.SessionOptions()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 1
            session = onnxruntime.InferenceSession(str(model), sess_options=options, providers=["CPUExecutionProvider"])
            _engine = Kokoro.from_session(session, str(voices))
        return _engine


@lru_cache(maxsize=16)
def kokoro_audio(text):
    import numpy
    samples, rate = _kokoro().create(text, voice="af_heart", speed=.95, lang="en-us")
    pcm = (numpy.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(pcm)
    return output.getvalue()


def synthesize(text):
    global _groq_blocked_until
    if time.monotonic() >= _groq_blocked_until:
        from .config import groq_client
        try:
            response = groq_client().with_options(max_retries=1, timeout=30).audio.speech.create(
                model="canopylabs/orpheus-v1-english", voice="hannah", input=text, response_format="wav")
            return response.content, "Hannah"
        except Exception:
            # Avoid repeated failing provider calls. The local neural model has
            # no account-terms activation and never sends narration off-server.
            _groq_blocked_until = time.monotonic() + 300
    return kokoro_audio(text), "Heart"
