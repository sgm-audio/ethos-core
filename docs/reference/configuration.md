# Configuration Reference

## Environment Variables

Defined in `.env.example`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ETHOS_HOST` | `0.0.0.0` | API server bind address |
| `ETHOS_PORT` | `8000` | API server port |
| `ETHOS_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `ETHOS_MAX_WORKERS` | `4` | Maximum concurrent processing workers |
| `ETHOS_OUTPUT_DIR` | `./output` | Default output directory |
| `RAY_ADDRESS` | `auto` | Ray cluster address for distributed processing |

## pyproject.toml

Key configuration sections:

### Ruff (Linting & Formatting)

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "C4", "SIM"]
```

### Pytest

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"
```

### Mypy

```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
ignore_missing_imports = true
check_untyped_defs = true
```

## Logging

ETHOS uses [Loguru](https://github.com/Delgan/loguru) for structured logging. Each agent logs to its module namespace (e.g., `ethos.agents.dsp.stage1.audio_analysis_agent`).

Set log level via environment variable:

```bash
export ETHOS_LOG_LEVEL=DEBUG
```
