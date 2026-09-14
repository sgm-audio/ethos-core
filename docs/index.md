# ETHOS Core

**Autonomous Audio Intelligence & Multi-Agent DSP Mastering Platform**

ETHOS Core is an AI-powered audio mastering system that uses 21 cooperative DSP agents and reinforcement learning to analyze, enhance, mix, and master audio files autonomously. It produces professional-quality results with DAW-ready exports, complete with SVG visualizations and REAPER project files.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **21 DSP Agents** | Four-stage pipeline: Analysis → Enhancement → Mastering → Export |
| **RL Multi-Agent System** | CriticAgent, EQRLAgent, DynamicsRLAgent with neural policy learning |
| **Drift Detection & Safe Mode** | Automatic fallback to deterministic heuristics when RL agents drift |
| **REAPER Project Generation** | Produces `.RPP` files with tracks, markers, and SVG curve visualizations |
| **Async Message Bus** | Priority-based pub/sub with W3C trace context propagation |
| **REST API + CLI** | FastAPI server with `/health`, `/metrics`, `/analyze` endpoints and full CLI |

## 🚀 Quick Start

```bash
# Install
git clone https://github.com/sgm-audio/ethos-core.git
cd ethos-core
uv sync --extra dev

# Analyze audio
uv run ethos analyze input.wav

# Start API server
uv run ethos serve --port 8000
```

## 📖 Documentation

- [Installation](tutorials/installation.md) — Set up your environment
- [Quickstart](tutorials/quickstart.md) — Process your first audio file
- [API Reference](reference/api.md) — REST endpoint documentation
- [Architecture](explanation/architecture.md) — System design and internals
