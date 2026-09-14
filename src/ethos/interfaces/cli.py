"""
ETHOS Command Line Interface
Unified CLI for audio analysis, stem separation, mastering, and serving the REST API.
"""

import argparse
import asyncio
import os
import sys

from ethos.agents.dsp.orchestrator import SEMASOrchestrator
from ethos.core.config import EnhancementProfile, TargetDAW, TargetFormat


def parse_args():
    parser = argparse.ArgumentParser(
        prog="ethos",
        description="ETHOS Audio Intelligence Platform CLI",
        epilog="Transform raw and AI-generated audio into professional DAW-ready productions",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: analyze
    analyze_parser = subparsers.add_parser(
        "analyze", help="Perform Stage 1 audio analysis on an audio file"
    )
    analyze_parser.add_argument("input_file", help="Path to input audio file (WAV, MP3, FLAC)")

    # Command: process
    process_parser = subparsers.add_parser(
        "process", help="Process audio track through 4-stage DSP pipeline"
    )
    process_parser.add_argument("input_file", help="Path to input audio file")
    process_parser.add_argument(
        "-o",
        "--output",
        dest="output_dir",
        default="./output",
        help="Output directory (default: ./output)",
    )
    process_parser.add_argument(
        "-p",
        "--profile",
        choices=["minimal", "balanced", "aggressive"],
        default="balanced",
        help="Enhancement profile",
    )
    process_parser.add_argument(
        "-f",
        "--format",
        choices=["streaming", "cd", "vinyl", "broadcast"],
        default="streaming",
        help="Target delivery format",
    )
    process_parser.add_argument(
        "-d",
        "--daw",
        choices=["reaper", "ableton", "logic"],
        default="reaper",
        help="Target DAW for project export",
    )
    process_parser.add_argument(
        "-r", "--reference", dest="reference_track", help="Optional reference track for matching"
    )

    # Command: serve
    serve_parser = subparsers.add_parser("serve", help="Start the ETHOS Core FastAPI REST server")
    serve_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host address (default: 0.0.0.0)",  # nosec B104
    )
    serve_parser.add_argument("--port", type=int, default=8000, help="Port number (default: 8000)")
    serve_parser.add_argument(
        "--reload", action="store_true", help="Enable hot reload for development"
    )

    return parser.parse_args()


async def run_analysis(input_file: str):
    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        sys.exit(1)

    print(f"Analyzing: {input_file}...")
    orchestrator = SEMASOrchestrator()
    analysis_agent = orchestrator.agents.get("audio_analysis")
    if not analysis_agent:
        print("Error: AudioAnalysisAgent not initialized")
        sys.exit(1)

    report = await analysis_agent.analyze_audio(input_file, "cli_analysis")
    print("\n--- Audio Analysis Report ---")
    print(f"  Duration:   {report.duration:.2f}s")
    print(f"  Sample Rate:{report.sample_rate} Hz ({report.channels} channels)")
    print(f"  Tempo:      {report.bpm:.1f} BPM (confidence: {report.bpm_confidence:.1%})")
    print(f"  Key:        {report.key} (confidence: {report.key_confidence:.1%})")
    print(f"  Genre:      {report.genre} ({report.subgenre})")
    print(f"  Sections:   {len(report.sections)} detected")
    for s in report.sections:
        print(f"    - {s.name:<12}: {s.start_time:.2f}s -> {s.end_time:.2f}s")
    print("-----------------------------\n")


async def run_process(args):
    if not os.path.exists(args.input_file):
        print(f"Error: File not found: {args.input_file}")
        sys.exit(1)

    print(f"Starting processing pipeline for: {args.input_file}")
    print(f"  Profile: {args.profile} | Format: {args.format} | DAW: {args.daw}")
    print(f"  Output:  {args.output_dir}\n")

    orchestrator = SEMASOrchestrator()
    job = await orchestrator.process_audio(
        input_file=args.input_file,
        output_directory=args.output_dir,
        enhancement_profile=EnhancementProfile(args.profile),
        target_format=TargetFormat(args.format),
        target_daw=TargetDAW(args.daw),
        reference_track=args.reference_track,
    )

    print(f"Job Status: {job.status.upper()} (Elapsed: {job.total_processing_time:.2f}s)")
    if job.status == "completed":
        print(f"  Output Directory: {job.output_directory}")
        if job.daw_project:
            print(f"  DAW Project:      {job.daw_project.project_file_path}")
    else:
        print(f"  Error: {job.error_message}")


def run_serve(args):
    import uvicorn

    print(f"Starting ETHOS API server on {args.host}:{args.port} (reload={args.reload})...")
    uvicorn.run("ethos.interfaces:app", host=args.host, port=args.port, reload=args.reload)


def main():
    args = parse_args()
    if args.command == "analyze":
        asyncio.run(run_analysis(args.input_file))
    elif args.command == "process":
        asyncio.run(run_process(args))
    elif args.command == "serve":
        run_serve(args)
    else:
        # Default help
        argparse.ArgumentParser(prog="ethos")
        print("Use 'ethos --help' for usage instructions.")


if __name__ == "__main__":
    main()
