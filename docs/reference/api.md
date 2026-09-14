# API Reference

Base URL: `http://localhost:8000`

## Endpoints

### `GET /`

Returns API information.

**Response:**
```json
{
  "name": "ETHOS Audio Intelligence Platform",
  "version": "0.1.0",
  "status": "operational",
  "agents": 21,
  "pipeline_stages": 4
}
```

---

### `GET /health`

Health check for liveness probes.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00.000000",
  "uptime_seconds": 3600.0,
  "active_jobs": 0,
  "system": {
    "cpu_percent": 15.2,
    "memory_percent": 42.1,
    "disk_percent": 55.0
  }
}
```

---

### `GET /metrics`

Prometheus-compatible metrics endpoint.

**Response** (text/plain):
```
# HELP ethos_active_agents Number of active ETHOS agents
# TYPE ethos_active_agents gauge
ethos_active_agents 21

# HELP ethos_jobs_total Total jobs processed
# TYPE ethos_jobs_total counter
ethos_jobs_total{status="completed"} 42
ethos_jobs_total{status="failed"} 1
ethos_jobs_total{status="total"} 43

# HELP ethos_pipeline_stages Number of DSP pipeline stages
# TYPE ethos_pipeline_stages gauge
ethos_pipeline_stages 4
```

---

### `POST /analyze`

Upload and analyze an audio file.

**Request:** `multipart/form-data` with `file` field

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@input.wav"
```

**Response:**
```json
{
  "file_id": "abc123",
  "status": "completed",
  "analysis": {
    "bpm": 120.0,
    "key": "C major",
    "genre": "Pop",
    "lufs": -14.2,
    "true_peak": -1.1,
    "sample_rate": 44100,
    "duration": 180.5,
    "channels": 2
  }
}
```

---

### `GET /jobs`

List all processing jobs.

### `GET /jobs/{job_id}`

Get status of a specific job.

## Error Codes

| Code | Description |
|------|-------------|
| `400` | Invalid file format or missing parameters |
| `404` | Job not found |
| `422` | Validation error |
| `500` | Internal processing error |
