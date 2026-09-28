from fastapi.testclient import TestClient

from clinic_mock.app import create_app
from clinic_mock.config import settings


def test_audio_fixtures_are_disabled_by_default(client) -> None:
    response = client.get("/test-fixtures/audio/manifest.json")

    assert response.status_code == 401


def test_enabled_audio_fixtures_are_public_and_valid_wav() -> None:
    original = settings.app.ENABLE_AUDIO_FIXTURES
    settings.app.ENABLE_AUDIO_FIXTURES = True
    try:
        with TestClient(create_app()) as client:
            manifest = client.get("/test-fixtures/audio/manifest.json")
            audio = client.get("/test-fixtures/audio/caller_name.wav")
    finally:
        settings.app.ENABLE_AUDIO_FIXTURES = original

    assert manifest.status_code == 200
    assert manifest.json()["synthetic"] is True
    assert {clip["clip_id"] for clip in manifest.json()["clips"]} == {
        "caller_name",
        "caller_dob",
    }
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/wav"
    assert audio.content[:4] == b"RIFF"
    assert audio.content[8:12] == b"WAVE"
