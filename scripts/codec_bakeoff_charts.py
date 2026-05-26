"""Render PNG charts from a codec bake-off JSON result file.

Reads codec_bakeoff_*.json from the local gitignored output directory (latest by default) and writes
chart images into web/public/codec/ for the public Track B page.

Charts produced:
    codec_bps_white.png       effective bits/sec vs SNR in white noise (one line per config)
    codec_bps_pink.png        same, pink noise
    codec_bps_reverb.png      same, reverb
    codec_clean_bps_bar.png   horizontal bar of clean-signal bits/sec per config
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "private" / "data"
DEFAULT_OUT_DIR = REPO_ROOT / "web" / "public" / "codec"

CONFIG_COLORS: Dict[str, str] = {
    "baseline":                            "#444444",
    "rep3x":                               "#1f77b4",
    "multiband":                           "#2ca02c",
    "ham74":                               "#9467bd",
    "pilot":                               "#ff7f0e",
    "multiband+pilot":                     "#17becf",
    "rep3x+ham74+pilot":                   "#d62728",
    "rep3x+multiband+ham74+pilot":         "#8c564b",
}


def latest_bakeoff(data_dir: Path) -> Path:
    candidates = sorted(data_dir.glob("codec_bakeoff_*.json"))
    if not candidates:
        raise FileNotFoundError(f"no codec_bakeoff_*.json in {data_dir}")
    return candidates[-1]


def render_snr_curves(cells: List[dict], configs: List[str],
                       noise: str, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.5), constrained_layout=True)
    for cfg in configs:
        rows = [c for c in cells if c["config_label"] == cfg and c["noise"] == noise]
        rows.sort(key=lambda r: r["snr_db"])
        xs = [r["snr_db"] for r in rows]
        ys = [r["eff_bits_per_sec"] for r in rows]
        color = CONFIG_COLORS.get(cfg, "#666")
        lw = 2.5 if cfg in ("baseline", "rep3x+ham74+pilot", "rep3x+multiband+ham74+pilot") else 1.4
        alpha = 1.0 if cfg in ("baseline", "rep3x+ham74+pilot", "rep3x+multiband+ham74+pilot") else 0.8
        ax.plot(xs, ys, label=cfg, color=color, linewidth=lw, alpha=alpha, marker="o", markersize=4)
    ax.set_xlabel("SNR (dB)", fontsize=11)
    ax.set_ylabel("Effective bits per second", fontsize=11)
    ax.set_title(f"Codec throughput vs noise: {noise}", fontsize=12, fontweight="bold")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper left", framealpha=0.85)
    ax.set_ylim(0, None)
    ax.invert_xaxis()  # higher SNR on the left (cleaner -> harder)
    plt.savefig(out_path, dpi=120)
    plt.close(fig)


def render_round_compare(cells: List[dict], baseline: str, feature: str,
                            noise_types: List[str], title: str,
                            out_path: Path) -> None:
    """Three-panel chart (one per noise type) comparing baseline vs a single
    round's feature config. Reads as 'what did this round buy.'"""
    fig, axes = plt.subplots(1, len(noise_types), figsize=(13.5, 4.0),
                                sharey=True, constrained_layout=True)
    if len(noise_types) == 1:
        axes = [axes]
    for ax, noise in zip(axes, noise_types):
        for cfg, color, label_suffix in [
            (baseline, "#444444", "(baseline)"),
            (feature,  CONFIG_COLORS.get(feature, "#1f77b4"), "(round)"),
        ]:
            rows = [c for c in cells if c["config_label"] == cfg and c["noise"] == noise]
            rows.sort(key=lambda r: r["snr_db"])
            xs = [r["snr_db"] for r in rows]
            ys = [r["eff_bits_per_sec"] for r in rows]
            ax.plot(xs, ys, label=f"{cfg} {label_suffix}", color=color,
                     linewidth=2.4, marker="o", markersize=5)
        ax.set_title(f"{noise} noise", fontsize=11)
        ax.set_xlabel("SNR (dB)")
        ax.grid(alpha=0.3)
        ax.invert_xaxis()
        ax.set_ylim(0, None)
    axes[0].set_ylabel("Effective bits per second")
    axes[-1].legend(fontsize=9, loc="upper right", framealpha=0.85)
    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.savefig(out_path, dpi=110)
    plt.close(fig)


def render_tradeoff_scatter(cells: List[dict], configs: List[str],
                                out_path: Path) -> None:
    """Two-panel scatter: x = clean-signal throughput, y = 1%-BER SNR floor.

    Left panel uses the white-noise floor; right uses reverb. We show both
    because they tell different stories: white noise pins almost every
    config at the same +15 dB cliff (so there's no differentiation along
    that axis), while reverb is where configurations actually spread out.
    Lower-right is the ideal corner in each panel (high throughput, works
    in worse channels).
    """
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.5), constrained_layout=True)

    for ax, noise, title in [
        (axes[0], "white",  "vs white-noise floor (the cliff is universal)"),
        (axes[1], "reverb", "vs reverb floor (where configs differentiate)"),
    ]:
        for cfg in configs:
            rows = [c for c in cells if c["config_label"] == cfg]
            clean_vals = [r["eff_bits_per_sec"] for r in rows if r["snr_db"] == 30.0]
            clean_bps = min(clean_vals) if clean_vals else 0.0
            usable = [r for r in rows if r["noise"] == noise and r["avg_ber"] <= 0.01]
            floor_db = min((r["snr_db"] for r in usable), default=35.0)
            color = CONFIG_COLORS.get(cfg, "#666")
            ax.scatter(clean_bps, floor_db, s=140, color=color, edgecolors="black",
                         linewidths=1.0, zorder=3)
            ax.annotate(cfg, (clean_bps, floor_db), xytext=(7, 5),
                          textcoords="offset points", fontsize=8)
        ax.set_xlabel("Clean throughput (bits per second)", fontsize=10)
        ax.set_ylabel(f"1%-BER floor in {noise} noise (dB SNR)\nlower = better", fontsize=10)
        ax.set_title(title, fontsize=11)
        ax.grid(alpha=0.3)
        ax.invert_yaxis()
        ax.set_xlim(0, None)

    fig.suptitle("Throughput vs noise-floor trade-off, by noise type",
                   fontsize=12, fontweight="bold")
    plt.savefig(out_path, dpi=120)
    plt.close(fig)


def render_clean_bar(cells: List[dict], configs: List[str], out_path: Path) -> None:
    # Clean-signal bits/sec at +30 dB white (worst case picked: take min across noise types)
    rows_at_30 = [c for c in cells if c["snr_db"] == 30.0]
    by_config: Dict[str, float] = {}
    for cfg in configs:
        bps_vals = [r["eff_bits_per_sec"] for r in rows_at_30 if r["config_label"] == cfg]
        if bps_vals:
            by_config[cfg] = min(bps_vals)  # worst-noise clean is the honest clean
    fig, ax = plt.subplots(figsize=(7.5, 4.5), constrained_layout=True)
    labels = list(by_config.keys())
    values = [by_config[k] for k in labels]
    colors = [CONFIG_COLORS.get(k, "#666") for k in labels]
    bars = ax.barh(range(len(labels)), values, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Effective bits per second at +30 dB SNR", fontsize=11)
    ax.set_title("Clean-signal throughput by configuration", fontsize=12, fontweight="bold")
    ax.grid(alpha=0.3, axis="x")
    ax.invert_yaxis()
    for bar, val in zip(bars, values):
        ax.text(val + 0.05, bar.get_y() + bar.get_height() / 2, f"{val:.2f}",
                  va="center", fontsize=9)
    ax.set_xlim(0, max(values) * 1.15)
    plt.savefig(out_path, dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=None,
                          help="path to codec_bakeoff_*.json (default: latest)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR,
                          help=f"output directory (default: {DEFAULT_OUT_DIR})")
    args = parser.parse_args()

    data_path = args.data or latest_bakeoff(DEFAULT_DATA_DIR)
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"reading {data_path}")
    payload = json.loads(data_path.read_text())
    cells = payload["cells"]
    configs = payload["configs"]
    for noise in payload["noise_types"]:
        out = args.out / f"codec_bps_{noise}.png"
        render_snr_curves(cells, configs, noise, out)
        try:
            print(f"  wrote {out.relative_to(REPO_ROOT)}")
        except ValueError:
            print(f"  wrote {out}")
    out = args.out / "codec_clean_bps_bar.png"
    render_clean_bar(cells, configs, out)
    try:
        print(f"  wrote {out.relative_to(REPO_ROOT)}")
    except ValueError:
        print(f"  wrote {out}")

    # Per-round head-to-head charts (baseline vs each round's single-feature config)
    rounds = [
        ("R1", "rep3x",     "Round 1: 3x symbol repetition vs baseline"),
        ("R2", "multiband", "Round 2: multi-band parallel symbols vs baseline"),
        ("R3", "ham74",     "Round 3: Hamming(7,4) FEC vs baseline"),
        ("R4", "pilot",     "Round 4: pilot tone calibration vs baseline"),
    ]
    for round_id, feature_cfg, title in rounds:
        out = args.out / f"codec_round_{round_id}.png"
        render_round_compare(cells, "baseline", feature_cfg,
                                payload["noise_types"], title, out)
        try:
            print(f"  wrote {out.relative_to(REPO_ROOT)}")
        except ValueError:
            print(f"  wrote {out}")

    out = args.out / "codec_tradeoff.png"
    render_tradeoff_scatter(cells, configs, out)
    try:
        print(f"  wrote {out.relative_to(REPO_ROOT)}")
    except ValueError:
        print(f"  wrote {out}")


if __name__ == "__main__":
    main()
