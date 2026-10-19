"""Speech-to-Text (STT) and Text-to-Speech (TTS) Evaluation & Test Harness.

Provides synthetic audio generation, WAV inspection, Word Error Rate (WER) /
Character Error Rate (CER) benchmark scoring, high-fidelity mock engines, and
verification suites for audio processing pipelines.
"""

from __future__ import annotations

import io
import math
import struct
import time
import wave
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from types import ModuleType
from typing import Any

# ─── Audio Sample Factory ───────────────────────────────────────────────────


class AudioSampleFactory:
    """Generates standard-compliant synthetic audio payloads for testing."""

    @staticmethod
    def create_wav(
        duration_seconds: float = 1.0,
        sample_rate: int = 16000,
        frequency_hz: float = 440.0,
        channels: int = 1,
        amplitude: float = 0.5,
    ) -> bytes:
        """Create a valid RIFF/WAVE PCM audio file with a synthetic sine wave."""
        buffer = io.BytesIO()
        total_samples = int(duration_seconds * sample_rate)
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # 16-bit PCM
            wav_file.setframerate(sample_rate)

            raw_frames = bytearray()
            for i in range(total_samples):
                sine_val = math.sin(2.0 * math.pi * frequency_hz * i / sample_rate)
                val = int(32767.0 * amplitude * sine_val)
                clamped = max(-32768, min(32767, val))
                frame = struct.pack("<h", clamped)
                if channels > 1:
                    frame = frame * channels
                raw_frames.extend(frame)

            wav_file.writeframes(raw_frames)
        return buffer.getvalue()

    @staticmethod
    def create_webm(payload_bytes: int = 256) -> bytes:
        """Create valid WebM audio starting with the standard EBML magic header."""
        # \x1a\x45\xdf\xa3 is the standard EBML signature expected by LifeSandbox
        header = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01\x42\xf2\x81\x04"
        padding = b"\x00" * max(0, payload_bytes - len(header))
        return header + padding

    @staticmethod
    def create_mp3(payload_bytes: int = 256) -> bytes:
        """Create valid MP3 audio starting with the ID3v2 container header."""
        header = b"ID3\x04\x00\x00\x00\x00\x00\x20" + b"\xff\xfb\x90\x44"
        padding = b"\x00" * max(0, payload_bytes - len(header))
        return header + padding

    @staticmethod
    def create_ogg(payload_bytes: int = 256) -> bytes:
        """Create valid Ogg audio starting with the OggS page signature."""
        header = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00"
        padding = b"\x00" * max(0, payload_bytes - len(header))
        return header + padding

    @staticmethod
    def create_corrupt(magic: bytes = b"BAD!") -> bytes:
        """Create corrupted audio data that fails container signature checks."""
        return magic + b"\x00" * 64

    @staticmethod
    def create_oversized(size_bytes: int = 21_000_000) -> bytes:
        """Create an audio payload exceeding the default 20MB limit."""
        riff_header = b"RIFF" + struct.pack("<I", size_bytes - 8) + b"WAVEfmt "
        return riff_header + (b"\x00" * (size_bytes - len(riff_header)))


# ─── WAV Audio Inspector ────────────────────────────────────────────────────


@dataclass(frozen=True)
class WavMetadata:
    """Inspected structural properties of a WAV audio stream."""

    channels: int
    sample_rate: int
    sample_width_bytes: int
    bits_per_sample: int
    frame_count: int
    duration_seconds: float
    is_valid: bool
    size_bytes: int


class WavAudioInspector:
    """Verifies compliance, headers, and audio parameters of WAV files."""

    @staticmethod
    def inspect(data: bytes) -> WavMetadata:
        if len(data) < 44 or not data.startswith(b"RIFF") or data[8:12] != b"WAVE":
            return WavMetadata(
                channels=0,
                sample_rate=0,
                sample_width_bytes=0,
                bits_per_sample=0,
                frame_count=0,
                duration_seconds=0.0,
                is_valid=False,
                size_bytes=len(data),
            )

        try:
            with wave.open(io.BytesIO(data), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_rate = wav_file.getframerate()
                sample_width = wav_file.getsampwidth()
                frame_count = wav_file.getnframes()
                duration = frame_count / sample_rate if sample_rate > 0 else 0.0

                return WavMetadata(
                    channels=channels,
                    sample_rate=sample_rate,
                    sample_width_bytes=sample_width,
                    bits_per_sample=sample_width * 8,
                    frame_count=frame_count,
                    duration_seconds=round(duration, 4),
                    is_valid=True,
                    size_bytes=len(data),
                )
        except Exception:
            return WavMetadata(
                channels=0,
                sample_rate=0,
                sample_width_bytes=0,
                bits_per_sample=0,
                frame_count=0,
                duration_seconds=0.0,
                is_valid=False,
                size_bytes=len(data),
            )


# ─── Speech Metrics: WER & CER Evaluation ───────────────────────────────────


class SpeechMetricsEvaluator:
    """Evaluates transcription fidelity using standard Levenshtein-based WER and CER."""

    @staticmethod
    def normalize_text(text: str) -> str:
        """Basic text normalization: lowercase, collapse whitespace, strip punctuation."""
        text = text.lower().strip()
        cleaned = []
        for char in text:
            if char.isalnum() or char.isspace():
                cleaned.append(char)
            else:
                cleaned.append(" ")
        return " ".join("".join(cleaned).split())

    @classmethod
    def compute_wer(cls, reference: str, hypothesis: str) -> float:
        """Compute Word Error Rate (WER = (S + D + I) / N)."""
        ref_words = cls.normalize_text(reference).split()
        hyp_words = cls.normalize_text(hypothesis).split()

        if not ref_words:
            return 0.0 if not hyp_words else 1.0

        d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]
        for i in range(len(ref_words) + 1):
            d[i][0] = i
        for j in range(len(hyp_words) + 1):
            d[0][j] = j

        for i in range(1, len(ref_words) + 1):
            for j in range(1, len(hyp_words) + 1):
                if ref_words[i - 1] == hyp_words[j - 1]:
                    d[i][j] = d[i - 1][j - 1]
                else:
                    substitution = d[i - 1][j - 1] + 1
                    insertion = d[i][j - 1] + 1
                    deletion = d[i - 1][j] + 1
                    d[i][j] = min(substitution, insertion, deletion)

        return round(d[len(ref_words)][len(hyp_words)] / len(ref_words), 4)

    @classmethod
    def compute_cer(cls, reference: str, hypothesis: str) -> float:
        """Compute Character Error Rate (CER = Levenshtein(ref, hyp) / len(ref))."""
        ref_chars = cls.normalize_text(reference).replace(" ", "")
        hyp_chars = cls.normalize_text(hypothesis).replace(" ", "")

        if not ref_chars:
            return 0.0 if not hyp_chars else 1.0

        d = [[0] * (len(hyp_chars) + 1) for _ in range(len(ref_chars) + 1)]
        for i in range(len(ref_chars) + 1):
            d[i][0] = i
        for j in range(len(hyp_chars) + 1):
            d[0][j] = j

        for i in range(1, len(ref_chars) + 1):
            for j in range(1, len(hyp_chars) + 1):
                if ref_chars[i - 1] == hyp_chars[j - 1]:
                    d[i][j] = d[i - 1][j - 1]
                else:
                    substitution = d[i - 1][j - 1] + 1
                    insertion = d[i][j - 1] + 1
                    deletion = d[i - 1][j] + 1
                    d[i][j] = min(substitution, insertion, deletion)

        return round(d[len(ref_chars)][len(hyp_chars)] / len(ref_chars), 4)

    @classmethod
    def evaluate(cls, reference: str, hypothesis: str) -> dict[str, Any]:
        """Compute complete transcription accuracy metric bundle."""
        wer = cls.compute_wer(reference, hypothesis)
        cer = cls.compute_cer(reference, hypothesis)
        return {
            "wer": wer,
            "cer": cer,
            "accuracy": round(max(0.0, 1.0 - wer), 4),
            "exact_match": cls.normalize_text(reference) == cls.normalize_text(hypothesis),
            "reference_words": len(cls.normalize_text(reference).split()),
            "hypothesis_words": len(cls.normalize_text(hypothesis).split()),
        }


# ─── Mock Speech Engines (For isolated unit & benchmark testing) ─────────────


@dataclass
class MockSegment:
    """Mock transcription segment returned by Whisper."""

    text: str
    start: float = 0.0
    end: float = 1.0


@dataclass
class MockTranscriptionInfo:
    """Mock transcription audio metadata."""

    language: str = "en"
    duration: float = 1.0


class MockWhisperModel:
    """Simulated Faster-Whisper model for deterministic benchmark execution."""

    def __init__(
        self,
        default_transcript: str = "Hello, this is a test transcription.",
        simulated_language: str = "en",
        simulated_duration: float = 2.5,
        fail_with: Exception | None = None,
    ):
        self.default_transcript = default_transcript
        self.simulated_language = simulated_language
        self.simulated_duration = simulated_duration
        self.fail_with = fail_with
        self.transcribe_calls: list[dict[str, Any]] = []

    def transcribe(
        self, audio_path: str, language: str | None = None
    ) -> tuple[list[MockSegment], MockTranscriptionInfo]:
        if self.fail_with:
            raise self.fail_with

        self.transcribe_calls.append({"audio_path": audio_path, "language": language})
        effective_lang = language or self.simulated_language
        segments = [
            MockSegment(text=part, start=i * 1.0, end=(i + 1) * 1.0)
            for i, part in enumerate(self.default_transcript.split(". "))
            if part.strip()
        ]
        info = MockTranscriptionInfo(
            language=effective_lang,
            duration=self.simulated_duration,
        )
        return segments, info


class MockKokoroPipeline:
    """Simulated Kokoro TTS pipeline returning audio arrays."""

    def __init__(self, sample_rate: int = 24000, duration_per_chunk: float = 0.5):
        self.sample_rate = sample_rate
        self.duration_per_chunk = duration_per_chunk
        self.calls: list[dict[str, Any]] = []

    def __call__(self, text: str, voice: str = "af_heart") -> list[tuple[str, str, Any]]:
        self.calls.append({"text": text, "voice": voice})
        samples_count = int(self.sample_rate * self.duration_per_chunk)
        fake_audio_array = [0.1 * math.sin(i / 10.0) for i in range(samples_count)]
        return [(text, "phonemes", fake_audio_array)]


@contextmanager
def mock_speech_environment(
    whisper_model: MockWhisperModel | None = None,
    kokoro_pipeline: MockKokoroPipeline | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Inject mock implementations of faster_whisper, kokoro, numpy, and soundfile."""
    import importlib.util
    import sys

    active_whisper = whisper_model or MockWhisperModel()
    active_kokoro = kokoro_pipeline or MockKokoroPipeline()

    mock_faster_whisper = ModuleType("faster_whisper")
    mock_faster_whisper.WhisperModel = lambda *args, **kwargs: active_whisper  # type: ignore

    mock_kokoro = ModuleType("kokoro")
    mock_kokoro.KPipeline = lambda *args, **kwargs: active_kokoro  # type: ignore

    mock_numpy = ModuleType("numpy")

    def mock_concat(parts: list[Any]) -> list[Any]:
        result = []
        for part in parts:
            result.extend(part)
        return result

    mock_numpy.concatenate = mock_concat  # type: ignore

    mock_soundfile = ModuleType("soundfile")

    def mock_write(buffer: io.BytesIO, data: Any, sample_rate: int, format: str = "WAV"):
        wav_bytes = AudioSampleFactory.create_wav(
            duration_seconds=max(0.1, len(data) / sample_rate),
            sample_rate=sample_rate,
        )
        buffer.write(wav_bytes)

    mock_soundfile.write = mock_write  # type: ignore

    orig_find_spec = importlib.util.find_spec

    def patched_find_spec(name: str, package: str | None = None):
        if name in {"faster_whisper", "kokoro", "numpy", "soundfile"}:
            spec = importlib.util.spec_from_loader(name, loader=None)
            return spec
        return orig_find_spec(name, package)

    modules_to_patch = {
        "faster_whisper": mock_faster_whisper,
        "kokoro": mock_kokoro,
        "numpy": mock_numpy,
        "soundfile": mock_soundfile,
    }

    saved_modules = {k: sys.modules.get(k) for k in modules_to_patch}
    for k, v in modules_to_patch.items():
        sys.modules[k] = v

    importlib.util.find_spec = patched_find_spec  # type: ignore

    try:
        yield {
            "whisper": active_whisper,
            "kokoro": active_kokoro,
        }
    finally:
        importlib.util.find_spec = orig_find_spec
        for k, v in saved_modules.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


# ─── Speech Harness Runner ──────────────────────────────────────────────────


@dataclass
class TestCaseResult:
    """Result of an individual test case evaluation."""

    name: str
    category: str  # "STT" or "TTS"
    passed: bool
    duration_ms: float
    details: dict[str, Any]
    error_message: str | None = None


class SpeechHarness:
    """Orchestrates comprehensive benchmark and regression suites for STT and TTS."""

    def __init__(self):
        self.results: list[TestCaseResult] = []

    def evaluate_text_preprocessing(self) -> list[TestCaseResult]:
        """Test markdown cleaning and sanitization rules for speech synthesis."""
        from app.services.speech import speech_text

        cases = [
            (
                "strip_markdown_headers_and_emphasis",
                "# Strategy Plan\nWe must prioritize **impact** and *clarity*.",
                "Strategy Plan We must prioritize impact and clarity.",
            ),
            (
                "omit_fenced_code_blocks",
                "Here is the code:\n```python\nimport sys\nprint('hello')\n```\nExecute it now.",
                "Here is the code: Code block omitted. Execute it now.",
            ),
            (
                "unwrap_markdown_links",
                "Check the [Project Roadmap](https://example.com/roadmap) for updates.",
                "Check the Project Roadmap for updates.",
            ),
            (
                "unwrap_markdown_images",
                "See diagram ![Architecture](https://example.com/arch.png) above.",
                "See diagram Architecture above.",
            ),
            (
                "unwrap_inline_code",
                "Run `uv run pytest` to execute the suite.",
                "Run uv run pytest to execute the suite.",
            ),
            (
                "preserve_clean_sentences",
                "We recommend maintaining six months of emergency runway.",
                "We recommend maintaining six months of emergency runway.",
            ),
        ]

        suite_results = []
        for name, input_text, expected_output in cases:
            start = time.perf_counter()
            actual = speech_text(input_text)
            passed = actual == expected_output
            duration_ms = (time.perf_counter() - start) * 1000.0

            res = TestCaseResult(
                name=f"TTS Preprocessing: {name}",
                category="TTS",
                passed=passed,
                duration_ms=round(duration_ms, 3),
                details={"input": input_text, "expected": expected_output, "actual": actual},
                error_message=None if passed else f"Expected '{expected_output}', got '{actual}'",
            )
            suite_results.append(res)
            self.results.append(res)

        return suite_results

    def generate_report(self) -> dict[str, Any]:
        """Generate structured JSON report of all executed speech harness tests."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        pass_rate = round((passed / total * 100.0), 2) if total > 0 else 0.0

        return {
            "summary": {
                "total_cases": total,
                "passed": passed,
                "failed": failed,
                "pass_rate_percent": pass_rate,
            },
            "cases": [
                {
                    "name": r.name,
                    "category": r.category,
                    "passed": r.passed,
                    "duration_ms": r.duration_ms,
                    "details": r.details,
                    "error": r.error_message,
                }
                for r in self.results
            ],
        }
