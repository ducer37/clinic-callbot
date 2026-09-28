"""Opt-in public synthetic WAV fixtures for HTTP audio development."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from clinic_mock.config import settings

audio_fixtures = APIRouter(prefix="/test-fixtures/audio", include_in_schema=False)

_CLIPS = {
    "caller_name": {
        "file": "caller_name.wav",
        "expected_transcript": "Tôi tên là Nguyễn Văn A.",
        "dialogue_step": "ASK_NAME",
    },
    "caller_dob": {
        "file": "caller_dob.wav",
        "expected_transcript": "Ngày sinh của tôi là ngày 14 tháng 3 năm 1978.",
        "dialogue_step": "ASK_DOB",
    },
}


def _fixture_path(filename: str) -> Path:
    return settings.app.AUDIO_FIXTURE_DIR / filename


@audio_fixtures.get("/manifest.json")
def audio_fixture_manifest() -> dict[str, object]:
    return {
        "synthetic": True,
        "clips": [
            {
                "clip_id": clip_id,
                "url_path": f"/test-fixtures/audio/{clip_id}.wav",
                "expected_transcript": metadata["expected_transcript"],
                "dialogue_step": metadata["dialogue_step"],
            }
            for clip_id, metadata in _CLIPS.items()
        ],
    }


@audio_fixtures.get("/{clip_id}.wav")
def get_audio_fixture(clip_id: str) -> FileResponse:
    metadata = _CLIPS.get(clip_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Audio fixture not found.")
    path = _fixture_path(metadata["file"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audio fixture file unavailable.")
    return FileResponse(
        path,
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=3600, immutable"},
    )
