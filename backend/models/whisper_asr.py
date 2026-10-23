import tempfile, os, logging

os.environ["PATH"] += r";C:\Users\VenkateshR\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin"

logger = logging.getLogger(__name__)

class WhisperASR:
    def __init__(self):
        self.model = None
        self.available = False
        self._load_model()

    def _load_model(self):
        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel("base", device="cpu", compute_type="int8")
            self.available = True
            logger.info("✅ Faster-Whisper ASR loaded")
        except Exception as e:
            logger.warning(f"⚠️  Whisper not available: {e}")

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> dict:
        if not self.model:
            return {"success": False, "text": "", "error": "Whisper ASR not available"}
        suffix = os.path.splitext(filename)[-1] or ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        try:
            segments, info = self.model.transcribe(
            tmp_path,
            language="en",
            beam_size=5,
            vad_filter=False
            )
            texts = []

            for seg in segments:
             print("SEGMENT:", seg.text)
             texts.append(seg.text)

            text = " ".join(texts).strip()
            print("FINAL:", text)
            return {"success": True, "text": text, "language": info.language}
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return {"success": False, "text": "", "error": str(e)}
        finally:
            try: os.unlink(tmp_path)
            except: pass

asr = WhisperASR()