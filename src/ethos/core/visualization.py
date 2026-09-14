"""
ETHOS DSP Visualization Engine
Generates user-facing SVG frequency response and dynamics transfer curves.
Provides deterministic, zero-dependency, high-performance visualization for DAW exports and API payloads.
"""

import math
import os
from typing import Any


def generate_eq_curve_svg(
    bands: list[dict[str, Any]],
    width: int = 800,
    height: int = 350,
) -> str:
    """
    Generate an SVG frequency response curve for a list of parametric EQ bands.
    Each band should specify 'freq' (Hz), 'gain' (dB), and 'q' (bandwidth factor).
    Frequency axis is logarithmic [20 Hz -> 20,000 Hz].
    Gain axis is linear [-18 dB -> +18 dB].
    """
    margin_left = 60
    margin_right = 30
    margin_top = 30
    margin_bottom = 40
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    f_min, f_max = 20.0, 20000.0
    log_f_min, log_f_max = math.log10(f_min), math.log10(f_max)
    gain_min, gain_max = -18.0, 18.0

    def f_to_x(f: float) -> float:
        norm = (math.log10(max(f, f_min)) - log_f_min) / (log_f_max - log_f_min)
        return margin_left + norm * plot_w

    def gain_to_y(g: float) -> float:
        norm = (g - gain_min) / (gain_max - gain_min)
        return margin_top + (1.0 - norm) * plot_h

    # Grid frequencies
    grid_freqs = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    grid_gains = [-12, -6, 0, 6, 12]

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">',
        f'<rect width="{width}" height="{height}" fill="#0f172a" rx="8"/>',
        f'<rect x="{margin_left}" y="{margin_top}" width="{plot_w}" height="{plot_h}" fill="#1e293b" rx="4"/>',
    ]

    # Frequency Grid Lines & Labels
    for gf in grid_freqs:
        gx = f_to_x(gf)
        svg_parts.append(
            f'<line x1="{gx:.1f}" y1="{margin_top}" x2="{gx:.1f}" y2="{margin_top + plot_h}" '
            f'stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>'
        )
        label = f"{gf}Hz" if gf < 1000 else f"{gf // 1000}kHz"
        svg_parts.append(
            f'<text x="{gx:.1f}" y="{margin_top + plot_h + 20}" fill="#94a3b8" '
            f'font-family="system-ui, sans-serif" font-size="11" text-anchor="middle">{label}</text>'
        )

    # Gain Grid Lines & Labels
    for gg in grid_gains:
        gy = gain_to_y(gg)
        stroke_color = "#64748b" if gg == 0 else "#334155"
        stroke_w = "1.5" if gg == 0 else "1"
        svg_parts.append(
            f'<line x1="{margin_left}" y1="{gy:.1f}" x2="{margin_left + plot_w}" y2="{gy:.1f}" '
            f'stroke="{stroke_color}" stroke-width="{stroke_w}"/>'
        )
        svg_parts.append(
            f'<text x="{margin_left - 10}" y="{gy + 4:.1f}" fill="#94a3b8" '
            f'font-family="system-ui, sans-serif" font-size="11" text-anchor="end">{gg:+d}dB</text>'
        )

    # Calculate magnitude response across 200 points
    num_pts = 200
    curve_pts = []
    for i in range(num_pts):
        alpha = i / (num_pts - 1)
        f = 10.0 ** (log_f_min + alpha * (log_f_max - log_f_min))
        total_gain_db = 0.0

        for b in bands:
            bf = float(b.get("freq", 1000.0))
            bg = float(b.get("gain", 0.0))
            bq = max(float(b.get("q", 1.0)), 0.1)

            # Peaking biquad approximation
            ratio = f / bf
            octaves = abs(math.log2(ratio + 1e-9))
            gain_contrib = bg * math.exp(-0.5 * (octaves * bq * 2.0) ** 2)
            total_gain_db += gain_contrib

        px = f_to_x(f)
        py = gain_to_y(total_gain_db)
        curve_pts.append(f"{px:.1f},{py:.1f}")

    points_str = " ".join(curve_pts)
    # Shaded area under curve
    zero_y = gain_to_y(0.0)
    area_pts = f"{margin_left},{zero_y} {points_str} {margin_left + plot_w},{zero_y}"
    svg_parts.append(f'<polygon points="{area_pts}" fill="rgba(56, 189, 248, 0.15)"/>')

    # Curve line
    svg_parts.append(
        f'<polyline points="{points_str}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>'
    )

    # Control points
    for b in bands:
        bf = float(b.get("freq", 1000.0))
        bg = float(b.get("gain", 0.0))
        bx = f_to_x(bf)
        by = gain_to_y(bg)
        svg_parts.append(
            f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="5" fill="#f59e0b" stroke="#ffffff" stroke-width="1.5"/>'
        )

    svg_parts.append(
        f'<text x="{width - margin_right}" y="20" fill="#38bdf8" font-family="system-ui, sans-serif" '
        f'font-size="12" font-weight="600" text-anchor="end">ETHOS Dynamic EQ Curve</text>'
    )
    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def generate_dynamics_curve_svg(
    threshold_db: float = -18.0,
    ratio: float = 4.0,
    knee_db: float = 4.0,
    makeup_db: float = 2.0,
    width: int = 400,
    height: int = 400,
) -> str:
    """
    Generate an SVG I/O transfer curve for a compressor/dynamics processor.
    Input range [-60 dBFS -> 0 dBFS], Output range [-60 dBFS -> 0 dBFS].
    """
    margin = 50
    plot_size = width - margin * 2
    min_db, max_db = -60.0, 0.0

    def db_to_xy(in_db: float, out_db: float) -> tuple[float, float]:
        x = margin + ((in_db - min_db) / (max_db - min_db)) * plot_size
        y = margin + (1.0 - (out_db - min_db) / (max_db - min_db)) * plot_size
        return x, y

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">',
        f'<rect width="{width}" height="{height}" fill="#0f172a" rx="8"/>',
        f'<rect x="{margin}" y="{margin}" width="{plot_size}" height="{plot_size}" fill="#1e293b" rx="4"/>',
    ]

    # Grid lines (-60, -40, -20, 0)
    for g_db in [-60, -40, -20, 0]:
        gx, gy = db_to_xy(g_db, g_db)
        # Vertical
        svg_parts.append(
            f'<line x1="{gx:.1f}" y1="{margin}" x2="{gx:.1f}" y2="{margin + plot_size}" stroke="#334155" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{gx:.1f}" y="{margin + plot_size + 18}" fill="#94a3b8" font-family="system-ui" font-size="10" text-anchor="middle">{g_db}</text>'
        )
        # Horizontal
        svg_parts.append(
            f'<line x1="{margin}" y1="{gy:.1f}" x2="{margin + plot_size}" y2="{gy:.1f}" stroke="#334155" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{margin - 8}" y="{gy + 3:.1f}" fill="#94a3b8" font-family="system-ui" font-size="10" text-anchor="end">{g_db}</text>'
        )

    # 1:1 Unity Line (dashed)
    x1, y1 = db_to_xy(min_db, min_db)
    x2, y2 = db_to_xy(max_db, max_db)
    svg_parts.append(
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#475569" stroke-width="1.5" stroke-dasharray="4,4"/>'
    )

    # Compression transfer curve calculation
    num_pts = 100
    curve_pts = []
    for i in range(num_pts):
        in_val = min_db + (i / (num_pts - 1)) * (max_db - min_db)
        if in_val <= threshold_db - (knee_db / 2.0):
            out_val = in_val
        elif in_val >= threshold_db + (knee_db / 2.0):
            out_val = threshold_db + (in_val - threshold_db) / ratio
        else:
            # Soft knee quadratic transition
            diff = in_val - threshold_db + (knee_db / 2.0)
            out_val = in_val + ((1.0 / ratio - 1.0) * (diff**2)) / (2.0 * knee_db)

        out_val = min(out_val + makeup_db, 0.0)
        cx, cy = db_to_xy(in_val, out_val)
        curve_pts.append(f"{cx:.1f},{cy:.1f}")

    svg_parts.append(
        f'<polyline points="{" ".join(curve_pts)}" fill="none" stroke="#ec4899" stroke-width="2.5" stroke-linejoin="round"/>'
    )

    # Threshold point marker
    tx, ty = db_to_xy(threshold_db, threshold_db + makeup_db)
    svg_parts.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="5" fill="#eab308"/>')

    svg_parts.append(
        f'<text x="{margin + 10}" y="{margin + 25}" fill="#ec4899" font-family="system-ui" font-size="12" font-weight="600">'
        f"Ratio: {ratio:.1f}:1 | Thr: {threshold_db:.0f}dB"
        f"</text>"
    )
    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def save_svg_to_file(svg_content: str, output_path: str) -> str:
    """Save generated SVG string to disk."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    return output_path
