# ETHOS Core implementation roadmap

This is a source-informed engineering plan, not a promise that every research feature is production-ready. “Fully functional” should mean predictable audio-in/audio-out behavior, truthful reporting, usable exports, durable job handling, tested deployment, and clearly scoped ML features.

## P0 — Correctness and honest behavior
- [x] Inventory TODOs, placeholders, incomplete implementations, and unconnected stages.
- [ ] Make API jobs transition queued → running → completed/failed, retain errors, and expose useful status/results.
- [ ] Ensure requests are validated (uploads, paths, format/profile/DAW) and resource limits/timeouts are enforced.
- [ ] Ensure pipeline errors are reflected in API/CLI exit status rather than silently presented as success.
- [ ] Replace guessed metrics/claims with measured values or explicitly label approximations; correct mastering ceiling/gain order.
- [ ] Define behavior when optional Demucs or ffmpeg is missing; do not silently claim stems/exports were produced.

## P1 — Connect the advertised end-to-end pipeline
- [ ] Route original audio through enhancement when separation is unavailable; currently the orchestrator advances through enhancement/mixing/mastering without processing audio.
- [ ] When stems are present, apply configured enhancement agents, then mixing/mastering and delivery conversion; persist each artifact and populate job metadata.
- [ ] Wire reference matching, loudness/frequency/genre agents only where supported by actual audio data.
- [ ] Implement requested DAW selection or reject unsupported Ableton/Logic targets instead of returning `None`.
- [ ] Make REAPER project generation produce valid, portable projects (escaped paths, correct tempo/time-signature, items/sources, markers, optional media copy).
- [ ] Implement MIDI transcription only with a documented supported method; otherwise clearly distinguish click-track generation from transcription.

## P2 — DSP quality and safety
- [ ] Replace heuristic or static DSP where the product promises dynamic processing; add parameter validation, finite-value checks, channel/sample-rate handling, and boundary tests.
- [ ] Measure true loudness (BS.1770/R128) and true peak; apply gain before final limiting and verify ceilings.
- [ ] Implement actual frequency-band EQ, genre-aware parameters, spectral reference matching, and measured quality metrics (or rename/document simplified behavior).
- [ ] Add listening-based evaluation plus synthetic regression tests for clipping, silence, mono/stereo, short clips, and non-44.1-kHz audio.

## P3 — Operational readiness
- [ ] Bound upload size, processing concurrency, output paths and job retention; use durable/background workers for production rather than in-process memory state.
- [ ] Add cancellation, progress events, structured errors, artifact download/cleanup, and persistent job storage.
- [ ] Secure API defaults (CORS, filesystem access, authentication if exposed); make health/readiness reflect dependency and agent status.
- [ ] Validate Docker/Kubernetes manifests and resource requests; test clean install, CLI, API, and supported OS/Python matrix in CI.
- [ ] Add end-to-end tests using generated audio and assert actual output artifacts and decoded audio properties.

## P4 — ML/RL research features
- [ ] Critic has no trained weights; confidence is currently a constant, and random initialization is not meaningful quality evaluation. Define uncertainty calibration and training/evaluation data protocol.
- [ ] Validate Critic tensor dimensions/input constraints, checkpoint compatibility, device behavior, and safe model loading.
- [ ] Connect EQ/dynamics proposals, HGO arbitration, critic rewards and bounded DSP actions to a reproducible training/evaluation loop; currently RL is separate from the pipeline.
- [ ] Document that “learning”/autonomous claims require datasets, baselines, reproducible benchmarks, and human listening evaluation.

## Verified implementation gaps (initial inventory)
- `stage4/daw_generator_agent.py`: Ableton and Logic methods are `pass`.
- `stage4/midi_generator_agent.py`: audio-to-MIDI is a placeholder; click-track generation is a distinct implemented feature.
- `stage1/stem_separator_agent.py`: drum/vocal specialized helpers return `None`; Demucs is optional and failure paths may return no stems.
- `rl/critic_agent.py`: confidence fixed at 0.8; model starts untrained unless a checkpoint is supplied.
- `agents/dsp/orchestrator.py`: stage 2/3 processing is largely skipped; format argument is not used; output directory can complete without a rendered audio artifact; target DAW is not dispatched.
- `interfaces/api.py`: background task errors can leave jobs queued; job records are in-memory and process-local; process accepts server filesystem paths; `/jobs` returns IDs only.
- Several DSP agents are deliberately simplified; see README’s implementation-status table and this roadmap’s P2.

## Execution order
Start with P0 job/API correctness and observable contracts, then P1 pipeline data flow and actual outputs, then DSP fidelity and operational hardening. Treat P4 as a separately gated research track rather than a prerequisite for reliable basic audio processing.
