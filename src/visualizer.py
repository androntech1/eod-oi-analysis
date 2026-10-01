import re
import matplotlib
matplotlib.use("Agg")  # Non-GUI backend for server/CI environments
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from pathlib import Path
from typing import Dict, Any

from .config import REPORTS_DIR, DOCS_DIR


def _t(s: str) -> str:
    """Strip supplementary-plane chars (emoji, symbols) that DejaVu Sans can't render."""
    return re.sub(r"[\U00010000-\U0010FFFF]", "", str(s)).strip()


class OIVisualizer:
    """Generates an Executive Intelligence Card with actionable insights, trapped writer alerts, and tactical setups."""

    def __init__(self):
        # Premium dark color palette
        self.bg_color = "#0b0f19"        # Deep obsidian
        self.panel_color = "#111827"     # Dark slate
        self.panel_alt = "#1f2937"       # Elevated slate
        self.border_color = "#374151"    # Border subtle
        self.text_main = "#f9fafb"       # Bright white
        self.text_muted = "#9ca3af"      # Slate gray
        self.ce_color = "#ef4444"        # Red (Calls / Resistance)
        self.pe_color = "#10b981"        # Emerald (Puts / Support)
        self.pain_color = "#f59e0b"      # Amber (Max Pain)
        self.spot_color = "#38bdf8"      # Cyan (Spot Price)

    def generate_chart(self, analysis_result: Dict[str, Any], history: list = None, filename: str = "latest_oi_chart.png") -> Path:
        """Create an executive intelligence card with visual data + tactical playbook."""
        weekly = analysis_result.get("weekly_analysis", {})
        shift = analysis_result.get("market_shift", {})
        playbook = weekly.get("playbook", {})

        symbol = weekly.get("symbol", "NIFTY")
        expiry = weekly.get("expiry", "")
        spot = weekly.get("underlying_price", 0.0)
        max_pain = weekly.get("max_pain", 0.0)
        totals = weekly.get("totals", {})
        atm_pcr = totals.get("atm_pcr_oi", 1.0)
        atm_pcr_chg = totals.get("atm_pcr_chg_oi", 1.0)
        regime = playbook.get("regime", "NEUTRAL").replace("_", " ")
        badge_color = playbook.get("color", "#f59e0b")
        sr = weekly.get("sr_levels", {})

        atm_strikes = weekly.get("atm_window_strikes", [])
        if not atm_strikes:
            return None

        # Filter strictly actionable ATM Window (14 strikes centered on ATM)
        atm_strike = weekly.get("atm_strike", spot)
        sorted_strikes = sorted(atm_strikes, key=lambda x: abs(x["strikePrice"] - atm_strike))[:14]
        sorted_strikes.sort(key=lambda x: x["strikePrice"])

        strikes = [s["strikePrice"] for s in sorted_strikes]
        ce_oi = [s["ce_oi"] / 100000 for s in sorted_strikes]
        pe_oi = [s["pe_oi"] / 100000 for s in sorted_strikes]
        ce_chg = [s["ce_chg_oi"] / 100000 for s in sorted_strikes]
        pe_chg = [s["pe_chg_oi"] / 100000 for s in sorted_strikes]

        # Layout: 4 rows x 2 cols
        #   Row 0 [full]: Header KPI bar
        #   Row 1 [left]: OI bar chart    | Row 1-2 [right]: Playbook (spans 2 rows)
        #   Row 2 [left]: Intraday change |
        #   Row 3 [full]: S/R trend (full width)
        fig = plt.figure(figsize=(18, 15), facecolor=self.bg_color)
        gs = fig.add_gridspec(
            4, 2,
            height_ratios=[0.09, 0.32, 0.32, 0.27],
            width_ratios=[1.15, 0.85],
            hspace=0.38, wspace=0.20
        )

        # ----------------- 1. Header & KPI Bar (full width) -----------------
        ax_header = fig.add_subplot(gs[0, :])
        ax_header.set_facecolor(self.bg_color)
        ax_header.axis("off")

        ax_header.text(0.01, 0.82, f"{symbol} EOD SMART MONEY & SHIFT INTELLIGENCE",
                       fontsize=20, weight="bold", color=self.text_main)
        ax_header.text(0.01, 0.50,
                       f"Expiry: {expiry}  |  Market Close: {weekly.get('timestamp', 'EOD')}  |  Actionable Battleground: ATM +/- 10 Strikes",
                       fontsize=11, color=self.text_muted)

        kpis = [
            ("SPOT PRICE", f"{spot:,.2f}", self.spot_color),
            ("MAX PAIN", f"{max_pain:,.0f}", self.pain_color),
            ("ATM PCR (OI)", f"{atm_pcr:.2f}", self.pe_color if atm_pcr >= 1.0 else self.ce_color),
            ("ATM CHG PCR", f"{atm_pcr_chg:.2f}", self.pe_color if atm_pcr_chg >= 1.0 else self.ce_color),
            ("EXPECTED BAND", playbook.get("expected_range", "N/A"), self.text_main),
            ("REGIME", regime, badge_color),
        ]

        card_width = 0.145
        start_x = 0.01
        for title, val, col in kpis:
            bbox = patches.FancyBboxPatch(
                (start_x, 0.0), card_width, 0.40,
                boxstyle="round,pad=0.02,rounding_size=0.03",
                facecolor=self.panel_color, edgecolor=self.border_color, linewidth=1.2,
                transform=ax_header.transAxes
            )
            ax_header.add_patch(bbox)
            ax_header.text(start_x + 0.01, 0.26, title, fontsize=8.5, weight="bold",
                           color=self.text_muted, transform=ax_header.transAxes)
            ax_header.text(start_x + 0.01, 0.06, val, fontsize=11.5, weight="bold",
                           color=col, transform=ax_header.transAxes)
            start_x += card_width + 0.022

        # ----------------- 2. Left-Top: Call vs Put OI -----------------
        ax_oi = fig.add_subplot(gs[1, 0])
        ax_oi.set_facecolor(self.panel_color)
        for spine in ax_oi.spines.values():
            spine.set_color(self.border_color)
        ax_oi.tick_params(colors=self.text_muted, labelsize=9.5)

        x = np.arange(len(strikes))
        bar_w = 0.38
        ax_oi.bar(x - bar_w / 2, ce_oi, width=bar_w, color=self.ce_color, label="Call OI (Resistance Wall)", alpha=0.9)
        ax_oi.bar(x + bar_w / 2, pe_oi, width=bar_w, color=self.pe_color, label="Put OI (Support Cushion)", alpha=0.9)

        ax_oi.set_xticks(x)
        ax_oi.set_xticklabels([f"{int(s)}" for s in strikes], rotation=35, ha="right")
        ax_oi.set_ylabel("Open Interest (Lakhs)", color=self.text_muted, fontsize=10)
        ax_oi.set_title("Actionable Open Interest Distribution (ATM +/- 7 Strikes)",
                         color=self.text_main, fontsize=12, weight="bold", pad=8)
        ax_oi.grid(color=self.border_color, linestyle="--", linewidth=0.5, alpha=0.6, axis="y")
        ax_oi.legend(facecolor=self.panel_color, edgecolor=self.border_color,
                     labelcolor=self.text_main, loc="upper right", fontsize=8.5)

        # Spot & Max Pain vertical markers
        spot_idx = np.argmin(np.abs(np.array(strikes) - spot))
        pain_idx = np.argmin(np.abs(np.array(strikes) - max_pain))
        ax_oi.axvline(spot_idx, color=self.spot_color, linestyle="--", linewidth=2.0, label="Spot")
        ax_oi.axvline(pain_idx, color=self.pain_color, linestyle=":", linewidth=2.0, label="Max Pain")

        # ----------------- 3. Left-Bottom: Intraday Additions / Unwinding -----------------
        ax_chg = fig.add_subplot(gs[2, 0])
        ax_chg.set_facecolor(self.panel_color)
        for spine in ax_chg.spines.values():
            spine.set_color(self.border_color)
        ax_chg.tick_params(colors=self.text_muted, labelsize=9.5)

        ax_chg.bar(x - bar_w / 2, ce_chg, width=bar_w, color=self.ce_color, label="Call Chg OI", alpha=0.85)
        ax_chg.bar(x + bar_w / 2, pe_chg, width=bar_w, color=self.pe_color, label="Put Chg OI", alpha=0.85)
        ax_chg.axhline(0, color=self.text_muted, linewidth=0.8)

        ax_chg.set_xticks(x)
        ax_chg.set_xticklabels([f"{int(s)}" for s in strikes], rotation=35, ha="right")
        ax_chg.set_ylabel("Net OI Change (Lakhs)", color=self.text_muted, fontsize=10)
        ax_chg.set_title("Intraday Writing vs Unwinding (Where Fresh Capital Moved)",
                          color=self.text_main, fontsize=12, weight="bold", pad=8)
        ax_chg.grid(color=self.border_color, linestyle="--", linewidth=0.5, alpha=0.6, axis="y")
        ax_chg.legend(facecolor=self.panel_color, edgecolor=self.border_color,
                      labelcolor=self.text_main, loc="upper right", fontsize=8.5)

        # ----------------- 4. Right: Tactical Playbook (spans rows 1 & 2) -----------------
        ax_intel = fig.add_subplot(gs[1:3, 1])
        ax_intel.set_facecolor(self.panel_color)
        for spine in ax_intel.spines.values():
            spine.set_color(self.border_color)
        ax_intel.axis("off")

        card_rect = patches.FancyBboxPatch(
            (0.02, 0.02), 0.96, 0.96,
            boxstyle="round,pad=0.03,rounding_size=0.03",
            facecolor=self.panel_alt, edgecolor=self.border_color, linewidth=1.5,
            transform=ax_intel.transAxes
        )
        ax_intel.add_patch(card_rect)

        ax_intel.text(0.06, 0.94, "INSTITUTIONAL PLAYBOOK & NEXT SESSION SETUP",
                      fontsize=13, weight="bold", color=self.text_main, transform=ax_intel.transAxes)

        shift_text = _t(shift.get("headline", "Consolidation pattern intact."))
        ax_intel.text(0.06, 0.87, "1. Market Regime & Structural Shift",
                      fontsize=11, weight="bold", color=self.spot_color, transform=ax_intel.transAxes)
        ax_intel.text(0.06, 0.81, f"{regime}: {_t(playbook.get('regime_desc', ''))}",
                      fontsize=10, color=self.text_main, transform=ax_intel.transAxes)
        ax_intel.text(0.06, 0.76, f">> {shift_text}",
                      fontsize=9.5, color=badge_color, transform=ax_intel.transAxes)

        trapped_lines = playbook.get("trapped_writers", ["No immediate trapped writers."])
        ax_intel.text(0.06, 0.69, "2. Trapped Writers & Risk Alert",
                      fontsize=11, weight="bold", color=self.spot_color, transform=ax_intel.transAxes)
        y_pos = 0.63
        for line in trapped_lines[:2]:
            ax_intel.text(0.06, y_pos, f"- {_t(line)}", fontsize=9.5,
                          color="#fca5a5" if "trapped" in line.lower() else self.text_muted,
                          transform=ax_intel.transAxes)
            y_pos -= 0.055

        ax_intel.text(0.06, 0.52, "3. Tactical Action Plan (Next Trading Session)",
                      fontsize=11, weight="bold", color=self.spot_color, transform=ax_intel.transAxes)

        ax_intel.text(0.06, 0.46, "[BULL] Confirmation Trigger:",
                      fontsize=10, weight="bold", color=self.pe_color, transform=ax_intel.transAxes)
        ax_intel.text(0.06, 0.41, _t(playbook.get("bullish_trigger", "")),
                      fontsize=9.5, color=self.text_main, transform=ax_intel.transAxes)

        ax_intel.text(0.06, 0.34, "[BEAR] Breakdown Trigger:",
                      fontsize=10, weight="bold", color=self.ce_color, transform=ax_intel.transAxes)
        ax_intel.text(0.06, 0.29, _t(playbook.get("bearish_trigger", "")),
                      fontsize=9.5, color=self.text_main, transform=ax_intel.transAxes)

        ax_intel.text(0.06, 0.22, "[RANGE] Intraday Corridor / Straddle Boundary:",
                      fontsize=10, weight="bold", color=self.pain_color, transform=ax_intel.transAxes)
        ax_intel.text(0.06, 0.17, _t(playbook.get("range_play", "")),
                      fontsize=9.5, color=self.text_main, transform=ax_intel.transAxes)

        ax_intel.text(0.06, 0.07,
                      "Smart Money Law: Trade with writer defense lines (S1/R1). Avoid chasing near ATM congestion.",
                      fontsize=8.5, style="italic", color=self.text_muted, transform=ax_intel.transAxes)

        # ----------------- 5. Bottom: S/R + Spot Migration (full width) -----------------
        ax_sr = fig.add_subplot(gs[3, :])
        ax_sr.set_facecolor(self.panel_color)
        for spine in ax_sr.spines.values():
            spine.set_color(self.border_color)
        ax_sr.tick_params(colors=self.text_muted, labelsize=9.5)

        hist = history or []
        if len(hist) >= 2:
            dates = [h["date"] for h in hist]
            spots_h = [h.get("underlying_price", 0) for h in hist]
            s1s = [h.get("support_1", 0) for h in hist]
            r1s = [h.get("resistance_1", 0) for h in hist]
            xs = list(range(len(dates)))

            ax_sr.plot(xs, spots_h, color=self.spot_color, linewidth=2.4, marker="o",
                       markersize=6, label="Spot Close", zorder=3)
            ax_sr.plot(xs, s1s, color=self.pe_color, linewidth=1.8, marker="s",
                       markersize=5, linestyle="--", label="Support S1 (Put Wall)", zorder=2)
            ax_sr.plot(xs, r1s, color=self.ce_color, linewidth=1.8, marker="^",
                       markersize=5, linestyle="--", label="Resistance R1 (Call Wall)", zorder=2)
            ax_sr.fill_between(xs, s1s, r1s, alpha=0.07, color=self.spot_color)

            # Label each point with its value
            for i, (sp, s1, r1) in enumerate(zip(spots_h, s1s, r1s)):
                ax_sr.annotate(f"{sp:,.0f}", (i, sp), textcoords="offset points",
                               xytext=(0, 8), ha="center", fontsize=8, color=self.spot_color)
                ax_sr.annotate(f"{s1:,.0f}", (i, s1), textcoords="offset points",
                               xytext=(0, -13), ha="center", fontsize=7.5, color=self.pe_color)
                ax_sr.annotate(f"{r1:,.0f}", (i, r1), textcoords="offset points",
                               xytext=(0, 8), ha="center", fontsize=7.5, color=self.ce_color)

            ax_sr.set_xticks(xs)
            ax_sr.set_xticklabels(dates, rotation=20, ha="right")
            ax_sr.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
            ax_sr.grid(color=self.border_color, linestyle="--", linewidth=0.5, alpha=0.6, axis="y")
            ax_sr.legend(facecolor=self.panel_color, edgecolor=self.border_color,
                         labelcolor=self.text_main, loc="upper left", fontsize=9.5,
                         ncol=3, framealpha=0.8)
        else:
            ax_sr.text(0.5, 0.5, "Accumulating history  (need >= 2 days)",
                       ha="center", va="center", color=self.text_muted, fontsize=12,
                       transform=ax_sr.transAxes)

        ax_sr.set_title("Support / Resistance / Spot Migration  (EOD Historical Trend)",
                         color=self.text_main, fontsize=12, weight="bold", pad=8)

        # Save to both reports/ and docs/
        report_path = REPORTS_DIR / filename
        docs_path = DOCS_DIR / filename

        plt.savefig(str(report_path), dpi=160, bbox_inches="tight", facecolor=self.bg_color)
        plt.savefig(str(docs_path), dpi=160, bbox_inches="tight", facecolor=self.bg_color)
        plt.close(fig)

        return report_path
