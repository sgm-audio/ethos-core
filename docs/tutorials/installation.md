# Installation

## Prerequisites

- **Python 3.10–3.12** (3.12 recommended)
- **[uv](https://docs.astral.sh/uv/)** — Fast Python package manager
- **ffmpeg** — Audio format conversion
- **libsndfile** — Audio file I/O

### Install System Dependencies

=== "macOS"
    ```bash
    brew install ffmpeg libsndfile
    ```

=== "Ubuntu/Debian"
    ```bash
    sudo apt-get install -y libsndfile1 ffmpeg
    ```

=== "Windows"
    ```powershell
    # Install via winget or chocolatey
    winget install FFmpeg
    # libsndfile is bundled with the Python soundfile package
    ```

## Install ETHOS Core

```bash
# Clone the repository
git clone https://github.com/sgm-audio/ethos-core.git
cd ethos-core

# Install all dependencies
uv sync --extra dev

# Verify installation
uv run ethos --help
```

## Optional: Ray Cluster

For distributed processing across multiple machines:

```bash
# Start Ray head node
ray start --head --port=6379

# Set the Ray address
export RAY_ADDRESS="ray://localhost:6379"
```

## Optional: Docker

```bash
docker build -t ethos-core .
docker run -p 8000:8000 ethos-core
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: demucs` | Stem separation requires Demucs. Install with `uv add demucs` |
| `libsndfile not found` | Install system package: `apt install libsndfile1` or `brew install libsndfile` |
| Windows `UV_LINK_MODE` error | Set `$env:UV_LINK_MODE="copy"` before running commands |
