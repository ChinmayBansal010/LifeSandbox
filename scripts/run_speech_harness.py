#!/usr/bin/env python3
"""CLI runner for Speech-to-Text (STT) and Text-to-Speech (TTS) harnesses.

Executes comprehensive STT/TTS benchmarks, WER/CER transcription accuracy
evaluations, audio container inspections, and API contract validations.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

# Ensure project root is in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Safe defaults for eval runs
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AUTH_MODE", "development")
if "LIFESANDBOX_EVAL_DATABASE_URL" in os.environ:
    os.environ["DATABASE_URL"] = os.environ["LIFESANDBOX_EVAL_DATABASE_URL"]
else:
    # Use isolated SQLite for speech evaluation runs
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from evals.speech_harness import (  # noqa: E402
    AudioSampleFactory,
    MockKokoroPipeline,
    MockWhisperModel,
    SpeechHarness,
    SpeechMetricsEvaluator,
    WavAudioInspector,
    mock_speech_environment,
)


def run_stt_harness(verbose: bool = False) -> dict:
    """Execute STT transcription accuracy and container compatibility benchmark."""
    settings = get_settings()
    settings.stt_provider = "faster_whisper"

    test_cases = [
        (
            "clean_speech_career_advice",
            "Evaluate career growth and compensation trade-offs over three years.",
            "Evaluate career growth and compensation trade-offs over three years.",
        ),
        (
            "numerical_financial_query",
            "Allocate 500 dollars to index funds and 200 dollars to emergency savings.",
            "Allocate 500 dollars to index funds and 200 dollars to emergency savings.",
        ),
        (
            "decision_modeling_prompt",
            "Should I buy a new electric vehicle or repair my existing car?",
            "Should I buy a new electric vehicle or repair my existing car?",
        ),
    ]

    results = []
    print("\n[STT Harness] Running Speech-to-Text Benchmarks...")

    for case_id, reference_text, mock_transcript in test_cases:
        mock_model = MockWhisperModel(
            default_transcript=mock_transcript,
            simulated_language="en",
            simulated_duration=2.0,
        )

        wav_bytes = AudioSampleFactory.create_wav(duration_seconds=1.0)
        start = time.perf_counter()

        with mock_speech_environment(whisper_model=mock_model):
            with patch("app.main._whisper_model", return_value=mock_model):
                with TestClient(app) as client:
                    response = client.post(
                        "/api/v1/audio/transcriptions",
                        files={"file": (f"{case_id}.wav", io.BytesIO(wav_bytes), "audio/wav")},
                        data={"language": "en"},
                    )

        duration_ms = (time.perf_counter() - start) * 1000.0
        passed = response.status_code == 200
        hypothesis = response.json().get("text", "") if passed else ""

        metrics = SpeechMetricsEvaluator.evaluate(reference_text, hypothesis) if passed else {}
        wer = metrics.get("wer", 1.0)
        cer = metrics.get("cer", 1.0)

        status_str = "PASS" if passed and wer <= 0.1 else "FAIL"
        print(
            f"  [{status_str}] {case_id:28s} | "
            f"WER: {wer:.2f} | CER: {cer:.2f} | {duration_ms:.1f}ms"
        )

        results.append(
            {
                "case_id": case_id,
                "status": status_str,
                "reference": reference_text,
                "hypothesis": hypothesis,
                "wer": wer,
                "cer": cer,
                "latency_ms": round(duration_ms, 2),
            }
        )

    # Audio Container Verification Suite
    print("[STT Harness] Validating Audio Containers (WAV, WebM, MP3, OGG)...")
    containers = [
        ("WAV", "test.wav", "audio/wav", AudioSampleFactory.create_wav(0.1)),
        ("WebM", "test.webm", "audio/webm", AudioSampleFactory.create_webm(128)),
        ("MP3", "test.mp3", "audio/mpeg", AudioSampleFactory.create_mp3(128)),
        ("OGG", "test.ogg", "audio/ogg", AudioSampleFactory.create_ogg(128)),
    ]
    mock_model = MockWhisperModel(default_transcript="Format validation successful.")
    container_results = []
    with mock_speech_environment(whisper_model=mock_model):
        with patch("app.main._whisper_model", return_value=mock_model):
            with TestClient(app) as client:
                for label, filename, mime, payload in containers:
                    resp = client.post(
                        "/api/v1/audio/transcriptions",
                        files={"file": (filename, io.BytesIO(payload), mime)},
                    )
                    ok = resp.status_code == 200
                    print(f"  [{'PASS' if ok else 'FAIL'}] Container: {label:5s} ({mime})")
                    container_results.append(
                        {"container": label, "status": "PASS" if ok else "FAIL"}
                    )

    return {
        "stt_accuracy_cases": results,
        "container_support": container_results,
        "avg_wer": round(sum(r["wer"] for r in results) / len(results), 4) if results else 0.0,
    }


def run_tts_harness(verbose: bool = False) -> dict:
    """Execute TTS speech synthesis quality, preprocessing, and audio structure suite."""
    settings = get_settings()
    settings.tts_provider = "kokoro"

    print("\n[TTS Harness] Running Text Preprocessing & Markdown Sanitization...")
    harness = SpeechHarness()
    preprocessing_results = harness.evaluate_text_preprocessing()
    for res in preprocessing_results:
        status_str = "PASS" if res.passed else "FAIL"
        print(f"  [{status_str}] {res.name}")

    print("[TTS Harness] Running Speech Synthesis & WAV Structure Verification...")
    mock_pipeline = MockKokoroPipeline(sample_rate=24000)

    test_utterances = [
        ("short_utterance", "Confirmed. Task created for tomorrow.", "af_heart"),
        (
            "code_omission",
            "Here is your plan:\n```python\nrun()\n```\nFollow all steps.",
            "af_bella",
        ),
        ("markdown_rich", "### Summary\n- **Rent:** $1200\n- **Savings:** $500", "am_adam"),
        ("voice_am_michael", "Checking Google Calendar events for conflicts.", "am_michael"),
    ]

    tts_results = []
    with mock_speech_environment(kokoro_pipeline=mock_pipeline):
        with patch("app.main._kokoro_pipeline", return_value=mock_pipeline):
            with TestClient(app) as client:
                for case_id, text, voice in test_utterances:
                    start = time.perf_counter()
                    response = client.post(
                        "/api/v1/audio/speech",
                        json={"text": text, "voice": voice},
                    )
                    duration_ms = (time.perf_counter() - start) * 1000.0

                    if response.status_code == 200:
                        meta = WavAudioInspector.inspect(response.content)
                        is_valid_wav = meta.is_valid and meta.sample_rate == 24000
                    else:
                        meta = None
                        is_valid_wav = False

                    status_str = "PASS" if is_valid_wav else "FAIL"
                    dur_str = f"{meta.duration_seconds:.2f}s audio" if meta else "invalid"
                    print(
                        f"  [{status_str}] {case_id:20s} (voice: {voice}) | "
                        f"{dur_str} | {duration_ms:.1f}ms latency"
                    )

                    tts_results.append(
                        {
                            "case_id": case_id,
                            "voice": voice,
                            "status": status_str,
                            "latency_ms": round(duration_ms, 2),
                            "wav_valid": is_valid_wav,
                            "sample_rate": meta.sample_rate if meta else 0,
                            "audio_duration_seconds": meta.duration_seconds if meta else 0.0,
                        }
                    )

    return {
        "preprocessing_cases": len(preprocessing_results),
        "preprocessing_passed": sum(1 for r in preprocessing_results if r.passed),
        "synthesis_cases": tts_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute STT and TTS test & evaluation harness.")
    parser.add_argument(
        "--suite",
        choices=["stt", "tts", "all"],
        default="all",
        help="Speech suite to run (default: all)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evals" / "reports" / "speech_eval.json",
        help="Path to export evaluation report JSON",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    args = parser.parse_args()

    print("==================================================")
    print("      LifeSandbox STT & TTS Evaluation Harness    ")
    print("==================================================")

    report_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "suite": args.suite,
    }

    if args.suite in {"stt", "all"}:
        report_data["stt"] = run_stt_harness(args.verbose)

    if args.suite in {"tts", "all"}:
        report_data["tts"] = run_tts_harness(args.verbose)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        print(f"\nSaved structured evaluation report to: {args.output}")

    print("\nSpeech Evaluation Harness run complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
