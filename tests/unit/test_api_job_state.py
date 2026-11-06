"""Regression tests for API background-job failure reporting."""

import pytest
from fastapi.testclient import TestClient

from ethos.interfaces import api


@pytest.mark.asyncio
async def test_process_job_records_unexpected_failure(tmp_path, monkeypatch):
    input_file = tmp_path / "input.wav"
    input_file.write_bytes(b"audio")

    async def fail_processing(**kwargs):
        raise RuntimeError("worker crashed")

    monkeypatch.setattr(api.orchestrator, "process_audio", fail_processing)
    api.jobs.clear()

    # Starlette's TestClient executes BackgroundTasks before returning the response.
    with TestClient(api.app) as client:
        response = client.post("/process", json={"input_file": str(input_file)})
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        status = client.get(f"/jobs/{job_id}")

    assert status.status_code == 200
    assert status.json()["status"] == "failed"
    assert status.json()["stage"] == "failed"
    assert status.json()["error_message"] == "worker crashed"
