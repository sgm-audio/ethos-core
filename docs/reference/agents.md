# Agent Catalog

ETHOS Core contains 21 specialized DSP agents organized into 4 pipeline stages.

## Stage 1: Analysis

| Agent | What it does | Key methods |
|-------|--------------|-------------|
| **AudioAnalysisAgent** | Works out BPM, key, sections and spectral features. Genre is a tempo/spectral rule of thumb. "LUFS" is RMS − 23 dB, not BS.1770 | `analyze_audio()` |
| **MetadataExtractorAgent** | Musical, technical and structural metadata | `extract_metadata()` |
| **StemSeparatorAgent** | Runs Demucs `htdemucs` (vocals, drums, bass, other), but only if Demucs is installed | `separate_stems()` |

## Stage 2: Enhancement

| Agent | What it does | Key methods |
|-------|--------------|-------------|
| **QualityEnhancementAgent** | Runs the stage-2 steps in sequence. There's no noise reduction | `enhance_stem()` |
| **TransientShapingAgent** | Splits transients from sustain using a Hilbert envelope | `shape_transients()` |
| **StereoEnhancementAgent** | Mid/side width; turns mono into pseudo-stereo | `enhance_stereo()` |
| **SpectralRepairAgent** | Blends the STFT magnitude with a smoothed copy | `repair_spectrum()` |
| **HarmonicEnrichmentAgent** | `tanh` saturation and exciter | `enrich_harmonics()` |
| **DynamicEnhancementAgent** | Sample-wise static compression/expansion | `enhance_dynamics()` |

## Stage 3: Mix and master

| Agent | What it does | Key methods |
|-------|--------------|-------------|
| **MixEngineerAgent** | Applies template mix parameters; every stem is panned centre | `create_mix()`, `apply_mix_to_stems()`, `render_mix()` |
| **MasteringAgent** | 30 Hz HPF, compression, clip limiter, then RMS gain | `master_audio()` |
| **LoudnessOptimizerAgent** | RMS-based loudness estimate and gain | `optimize_loudness()` |
| **FrequencyBalanceAgent** | One 20 Hz high-pass | `balance_frequency()` |
| **GenreOptimizerAgent** | Applies broadband gain per genre | `optimize_for_genre()` |
| **ReferenceMatchingAgent** | Matches the RMS level of a reference | `match_reference()` |

## Stage 4: Export

| Agent | What it does | Key methods |
|-------|--------------|-------------|
| **DAWGeneratorAgent** | Writes a REAPER `.RPP` project and SVG curves | `generate_reaper_project()` |
| **MarkerCreatorAgent** | Creates timeline markers from the section analysis | `create_markers()` |
| **TempoMapAgent** | Builds a constant-BPM tempo map | `create_tempo_map()` |
| **MetadataExporterAgent** | Writes JSON and XML reports (nothing is embedded in the audio) | `export_to_json()`, `export_to_xml()` |
| **FormatConverterAgent** | WAV/FLAC via soundfile; MP3/OGG via ffmpeg | `convert_to_format()` |
| **MIDIGeneratorAgent** | Click-track MIDI; transcription is a placeholder | `create_click_track_midi()`, `generate_midi_from_audio()` |

## RL Agents

| Agent | Description |
|-------|-------------|
| **CriticAgent** | Small PyTorch MLP that scores feature vectors. No trained weights are included |
| **EQRLAgent** | Actor-critic EQ parameter agent (experimental, not wired into the pipeline) |
| **DynamicsRLAgent** | Actor-critic dynamics parameter agent (experimental, not wired into the pipeline) |
| **HGOCoordinator** | Hierarchical Goal Optimization conflict resolution |
| **ConceptDriftDetector** | Monitors RL policy drift and engages Safe Mode |
