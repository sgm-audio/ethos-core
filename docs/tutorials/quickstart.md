# Quickstart

Process your first audio file in under 5 minutes.

## 1. Analyze Audio

```bash
uv run ethos analyze input.wav
```

This runs the Stage 1 analysis pipeline and outputs:

- **BPM** detection
- **Key** and scale estimation
- **Genre** classification
- **Loudness** (LUFS) and peak measurements
- **Section** boundaries (verse, chorus, bridge)

## 2. Full Pipeline Processing

```bash
uv run ethos process input.wav -o output/
```

This runs all 4 stages:

1. **Analysis** — Feature extraction, metadata, stem separation
2. **Enhancement** — Noise reduction, transient shaping, spectral repair
3. **Mastering** — Mix balance, loudness optimization, genre matching
4. **Export** — REAPER `.RPP` project, format conversion, metadata embedding

## 3. Start the API Server

```bash
uv run ethos serve --port 8000
```

### Upload via API

```bash
# Health check
curl http://localhost:8000/health

# Analyze a file
curl -X POST http://localhost:8000/analyze \
  -F "file=@input.wav"

# Check Prometheus metrics
curl http://localhost:8000/metrics

# List processing jobs
curl http://localhost:8000/jobs
```

## 4. View Results

After processing, the `output/` directory contains:

```
output/
├── mastered.wav          # Final mastered audio
├── session.RPP           # REAPER project file
├── session_eq_curve.svg  # EQ frequency response visualization
├── session_dynamics_curve.svg  # Compressor transfer curve
└── metadata.json         # Extracted audio metadata
```

## Next Steps

- [Process Audio Files](../how-to/process-audio.md) — Advanced processing options
- [Configure RL Agents](../how-to/configure-rl-agents.md) — Tune the AI mastering
- [API Reference](../reference/api.md) — Full endpoint documentation
