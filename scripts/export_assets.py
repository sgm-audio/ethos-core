#!/usr/bin/env python3
"""
ETHOS Asset Finalization & SBOM Compiler
1. Exports compiled FastAPI OpenAPI specification (openapi.json).
2. Generates CycloneDX Software Bill of Materials (SBOM) for dependencies.
"""

import importlib.metadata
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

from ethos.interfaces.api import app  # noqa: E402


def export_openapi_schema(dist_dir: Path) -> Path:
    """Export the live OpenAPI 3.1.0 schema to JSON."""
    schema = app.openapi()
    openapi_path = dist_dir / "openapi.json"
    with open(openapi_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"[OK] Exported OpenAPI schema -> {openapi_path}")
    return openapi_path


def export_cyclonedx_sbom(dist_dir: Path) -> Path:
    """
    Generate a valid CycloneDX v1.5 JSON Software Bill of Materials (SBOM)
    enumerating all installed Python packages, versions, and licenses.
    """
    components = []

    # Collect installed distributions
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name", "")
        version = dist.metadata.get("Version", "")
        license_name = dist.metadata.get("License", "Unknown")
        summary = dist.metadata.get("Summary", "")

        if not name:
            continue

        component = {
            "type": "library",
            "name": name,
            "version": version,
            "description": summary,
            "licenses": [{"license": {"name": license_name}}],
            "purl": f"pkg:pypi/{name.lower()}@{version}",
        }
        components.append(component)

    # Sort components deterministically
    components.sort(key=lambda c: c["name"].lower())

    sbom_data = {
        "$schema": "http://cyclonedx.org/schema/bom-1.5.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(),
            "tools": [{"vendor": "ETHOS Core", "name": "AssetCompiler", "version": "0.1.0"}],
            "component": {
                "type": "application",
                "name": "ethos-core",
                "version": "0.1.0",
                "description": "Autonomous Audio Intelligence & Multi-Agent DSP Mastering Platform",
                "licenses": [{"license": {"id": "MIT"}}],
            },
        },
        "components": components,
    }

    sbom_path = dist_dir / "sbom.json"
    with open(sbom_path, "w", encoding="utf-8") as f:
        json.dump(sbom_data, f, indent=2)
    print(f"[OK] Generated CycloneDX SBOM ({len(components)} components) -> {sbom_path}")
    return sbom_path


def main():
    dist_dir = root_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    print(f"Finalizing release artifacts into {dist_dir}...")

    export_openapi_schema(dist_dir)
    export_cyclonedx_sbom(dist_dir)
    print("Asset finalization complete.")


if __name__ == "__main__":
    main()
