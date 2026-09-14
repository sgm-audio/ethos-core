# CLI Reference

## Commands

### `ethos analyze`

Analyze an audio file and output metadata.

```bash
uv run ethos analyze <input_file> [options]
```

| Option | Description |
|--------|-------------|
| `--format json` | Output format (json, text) |
| `--verbose` | Enable debug logging |

---

### `ethos process`

Run the full 4-stage DSP pipeline.

```bash
uv run ethos process <input_file> -o <output_dir> [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | Required | Output directory |
| `--target-lufs` | `-14.0` | Target integrated loudness |
| `--genre` | Auto-detect | Genre hint |
| `--format` | `wav` | Output format (wav, flac, mp3) |

---

### `ethos serve`

Start the FastAPI REST server.

```bash
uv run ethos serve [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `8000` | Port number |
| `--workers` | `1` | Number of workers |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Invalid arguments |
