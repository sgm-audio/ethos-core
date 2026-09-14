"""
Unit tests for ethos.interfaces:
- FastAPI REST API endpoints
- Command Line Interface (CLI)
"""

import pytest
from starlette.testclient import TestClient

from ethos.interfaces.api import app
from ethos.interfaces.cli import parse_args


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


def test_api_root(client: TestClient):
    """Verify root metadata endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "ETHOS Core Audio Intelligence API"
    assert data["status"] == "operational"


def test_api_health_check(client: TestClient):
    """Verify healthcheck probe returns active agents count and 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["active_agents"] == 21


def test_api_analyze_upload(client: TestClient, synthetic_stereo_wav: str):
    """Verify audio file upload and analysis endpoint."""
    with open(synthetic_stereo_wav, "rb") as f:
        response = client.post(
            "/analyze",
            files={"file": ("test.wav", f, "audio/wav")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "bpm" in data
    assert "key" in data
    assert "genre" in data
    assert data["bpm"] > 0


def test_api_jobs_endpoints(client: TestClient):
    """Verify jobs listing and 404 for missing job."""
    list_resp = client.get("/jobs")
    assert list_resp.status_code == 200
    assert isinstance(list_resp.json(), list)

    missing_resp = client.get("/jobs/nonexistent_id")
    assert missing_resp.status_code == 404


def test_cli_argument_parsing(monkeypatch):
    """Verify CLI parser options for analyze, process, and serve."""
    monkeypatch.setattr("sys.argv", ["ethos", "analyze", "test.wav"])
    args = parse_args()
    assert args.command == "analyze"
    assert args.input_file == "test.wav"

    monkeypatch.setattr(
        "sys.argv",
        ["ethos", "process", "input.wav", "-o", "./custom_out", "-p", "aggressive", "-d", "reaper"],
    )
    args_proc = parse_args()
    assert args_proc.command == "process"
    assert args_proc.output_dir == "./custom_out"
    assert args_proc.profile == "aggressive"
    assert args_proc.daw == "reaper"

    monkeypatch.setattr("sys.argv", ["ethos", "serve", "--port", "9000"])
    args_serve = parse_args()
    assert args_serve.command == "serve"
    assert args_serve.port == 9000


@pytest.mark.asyncio
async def test_cli_run_analysis(synthetic_stereo_wav: str, capsys):
    """Verify CLI run_analysis prints report."""
    from ethos.interfaces.cli import run_analysis

    await run_analysis(synthetic_stereo_wav)
    captured = capsys.readouterr()
    assert "Audio Analysis Report" in captured.out
    assert "Duration:" in captured.out
    assert "Tempo:" in captured.out
