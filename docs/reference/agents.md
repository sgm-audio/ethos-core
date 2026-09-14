# Agent Catalog

ETHOS Core contains 21 specialized DSP agents organized into 4 pipeline stages.

## Stage 1 — Analysis

| Agent | Description | Key Methods |
|-------|-------------|-------------|
| **AudioAnalysisAgent** | Extracts BPM, key, genre, loudness, spectral features | `analyze_audio()` |
| **MetadataExtractorAgent** | Reads and writes audio file metadata tags | `extract_metadata()` |
| **StemSeparatorAgent** | Separates audio into vocals, drums, bass, other using Demucs | `separate_stems()` |

## Stage 2 — Enhancement

| Agent | Description | Key Methods |
|-------|-------------|-------------|
| **QualityEnhancementAgent** | Noise reduction and signal cleanup | `enhance_quality()` |
| **TransientShapingAgent** | Adjusts attack/sustain of transient events | `shape_transients()` |
| **StereoEnhancementAgent** | Stereo width and imaging adjustments | `enhance_stereo()` |
| **SpectralRepairAgent** | Repairs spectral artifacts and gaps | `repair_spectral()` |
| **HarmonicEnhancementAgent** | Adds harmonic richness via saturation | `enhance_harmonics()` |
| **DynamicEnhancementAgent** | Dynamic range optimization | `enhance_dynamics()` |

## Stage 3 — Mastering

| Agent | Description | Key Methods |
|-------|-------------|-------------|
| **MixEngineerAgent** | Stem level balancing and panning | `mix_stems()` |
| **MasteringAgent** | Full mastering chain (EQ, compression, limiting) | `master_audio()` |
| **LoudnessOptimizerAgent** | LUFS-targeted loudness normalization | `optimize_loudness()` |
| **FrequencyBalanceAgent** | Spectral balance correction | `balance_frequencies()` |
| **GenreMatchingAgent** | Genre-appropriate processing profiles | `match_genre()` |
| **ReferenceMatchingAgent** | Match tonal characteristics of a reference track | `match_reference()` |

## Stage 4 — Export

| Agent | Description | Key Methods |
|-------|-------------|-------------|
| **DAWGeneratorAgent** | Generates REAPER `.RPP` project files with SVG curves | `generate_reaper_project()` |
| **MarkerAgent** | Creates timeline markers from section analysis | `create_markers()` |
| **TempoMapAgent** | Builds tempo maps from BPM analysis | `create_tempo_map()` |
| **MetadataExporterAgent** | Embeds metadata into output files | `export_metadata()` |
| **FormatConverterAgent** | Converts between audio formats (WAV, FLAC, MP3) | `convert_to_format()` |
| **MIDIGeneratorAgent** | Generates MIDI representations from audio | `generate_midi()` |

## RL Agents

| Agent | Description |
|-------|-------------|
| **CriticAgent** | Neural network quality evaluator (satisfaction scoring) |
| **EQRLAgent** | Policy gradient EQ parameter learning |
| **DynamicsRLAgent** | Policy gradient dynamics parameter learning |
| **HGOCoordinator** | Hierarchical Goal Optimization conflict resolution |
| **ConceptDriftDetector** | Monitors RL policy drift and engages Safe Mode |
