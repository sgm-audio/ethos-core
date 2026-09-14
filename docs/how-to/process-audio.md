# Process Audio Files

## Single File Processing

```bash
uv run ethos process input.wav -o output/
```

### Customizing Parameters

```bash
# Target loudness (LUFS)
uv run ethos process input.wav -o output/ --target-lufs -14.0

# Genre hint for style-appropriate processing
uv run ethos process input.wav -o output/ --genre rock

# Output format
uv run ethos process input.wav -o output/ --format flac
```

## Working with Stems

ETHOS automatically separates audio into stems (vocals, drums, bass, other) during Stage 1 processing using Demucs. Each stem is processed independently through the enhancement pipeline.

```bash
# Process with stem separation
uv run ethos process input.wav -o output/ --separate-stems
```

The separated stems are available in the REAPER project file for individual track editing.

## Generating REAPER Projects

Every processing run produces a REAPER `.RPP` project file with:

- **Individual stem tracks** with proper naming and color-coding
- **Section markers** (verse, chorus, bridge) from analysis
- **Tempo map** synced to detected BPM
- **SVG visualizations** — EQ frequency response and dynamics transfer curves

## Batch Processing

```bash
# Process all WAV files in a directory
for f in input_dir/*.wav; do
  uv run ethos process "$f" -o "output/$(basename "$f" .wav)/"
done
```

## API-Based Processing

```bash
# Upload and process via REST API
curl -X POST http://localhost:8000/analyze \
  -F "file=@input.wav" \
  -H "Content-Type: multipart/form-data"
```
