import matplotlib
matplotlib.use("Agg")  # Non-GUI backend for server/CI environments
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from pathlib import Path
from typing import Dict, Any

from .config import REPORTS_DIR, DOCS_DIR

class OIVisualizer:
    """Generates modern dark-mode visual analytics cards and charts for GitHub."""

    def __init__(self):
        # Premium dark color palette
        self.bg_color = "#0f172a"        # Dark slate
        self.panel_color = "#1e293b"     # Card slate
        self.border_color = "#334155"    # Subtle border
        self.text_main = "#f8fafc"       # White
        self.text_muted = "#94a3b8"      # Slate 400
        self.ce_color = "#f43f5e"        # Rose Red (Calls / Resistance)
        self.pe_color = "#10b981"        # Emerald Green (Puts / Support)
        self.pain_color = "#f59e0b"      # Amber (Max Pain)
        self.spot_color = "#38bdf8"      # Sky Blue (Spot Price)

    def generate_chart(self, analysis_result: Dict[str, Any], filename: str = "latest_oi_chart.png") -> Path:
        """Create publication-grade dark mode visual chart."""
        weekly = analysis_result.get("weekly_analysis", {})
        shift = analysis_result.get("market_shift", {})

        symbol = weekly.get("symbol", "NIFTY")
        expiry = weekly.get("expiry", "")
        spot = weekly.get("underlying_price", 0.0)
        max_pain = weekly.get("max_pain", 0.0)
        totals = weekly.get("totals", {})
        pcr_oi = totals.get("pcr_oi", 1.0)
        pcr_chg = totals.get("pcr_chg_oi", 1.0)
        sentiment = weekly.get("sentiment", {})
        verdict = sentiment.get("verdict", "NEUTRAL").replace("_", " ")
        badge_color = sentiment.get("badge_color", "#fbbf24")
        sr = weekly.get("sr_levels", {})

        atm_strikes = weekly.get("atm_window_strikes", [])
        if not atm_strikes:
            return None

        # Take around 16 strikes centered around ATM
        atm_strike = weekly.get("atm_strike", spot)
        sorted_strikes = sorted(atm_strikes, key=lambda x: abs(x["strikePrice"] - atm_strike))[:16]
        sorted_strikes.sort(key=lambda x: x["strikePrice"])

        strikes = [s["strikePrice"] for s in sorted_strikes]
        ce_oi = [s["ce_oi"] / 100000 for s in sorted_strikes]      # in Lakhs
        pe_oi = [s["pe_oi"] / 100000 for s in sorted_strikes]      # in Lakhs
        ce_chg = [s["ce_chg_oi"] / 100000 for s in sorted_strikes]  # in Lakhs
        pe_chg = [s["pe_chg_oi"] / 100000 for s in sorted_strikes]  # in Lakhs

        # Setup figure
        fig = plt.figure(figsize=(16, 10), facecolor=self.bg_color)
        gs = fig.add_gridspec(3, 2, height_ratios=[0.18, 0.41, 0.41], hspace=0.35, wspace=0.22)

        # ----------------- Top Header & Metric Badges -----------------
        ax_header = fig.add_subplot(gs[0, :])
        ax_header.set_facecolor(self.bg_color)
        ax_header.axis("off")

        # Title
        ax_header.text(
            0.01, 0.82,
            f"{symbol} EOD OPEN INTEREST & MARKET DIRECTION ANALYSIS",
            fontsize=20, weight="bold", color=self.text_main
        )
        ax_header.text(
            0.01, 0.48,
            f"Expiry: {expiry}  |  Market Timestamp: {weekly.get('timestamp', 'EOD')}  |  Shift: {shift.get('shift_status', 'ACTIVE')}",
            fontsize=12, color=self.text_muted
        )

        # KPI Badges
        kpis = [
            ("SPOT PRICE", f"{spot:,.2f}", self.spot_color),
            ("MAX PAIN", f"{max_pain:,.0f}", self.pain_color),
            ("PCR (OI)", f"{pcr_oi:.2f}", self.pe_color if pcr_oi >= 1.0 else self.ce_color),
            ("PCR (CHG)", f"{pcr_chg:.2f}", self.pe_color if pcr_chg >= 1.0 else self.ce_color),
            ("VERDICT", verdict, badge_color)
        ]

        card_width = 0.16
        start_x = 0.01
        card_y = 0.02
        for title, val, col in kpis:
            bbox = patches.FancyBboxPatch(
                (start_x, card_y), card_width, 0.38,
                boxstyle="round,pad=0.02,rounding_size=0.03",
                facecolor=self.panel_color, edgecolor=self.border_color, linewidth=1.2,
                transform=ax_header.transAxes
            )
            ax_header.add_patch(bbox)
            ax_header.text(start_x + 0.01, card_y + 0.24, title, fontsize=9, weight="bold", color=self.text_muted, transform=ax_header.transAxes)
            ax_header.text(start_x + 0.01, card_y + 0.07, val, fontsize=12, weight="bold", color=col, transform=ax_header.transAxes)
            start_x += card_width + 0.035

        # ----------------- Panel 1: Call vs Put Total OI -----------------
        ax_oi = fig.add_subplot(gs[1, :])
        ax_oi.set_facecolor(self.panel_color)
        ax_oi.spines["bottom"].set_color(self.border_color)
        ax_oi.spines["top"].set_color(self.border_color)
        ax_oi.spines["left"].set_color(self.border_color)
        ax_oi.spines["right"].set_color(self.border_color)
        ax_oi.tick_params(colors=self.text_muted, labelsize=10)

        x_indices = np.arange(len(strikes))
        bar_w = 0.36

        bars_ce = ax_oi.bar(x_indices - bar_w/2, ce_oi, width=bar_w, color=self.ce_color, label="Call OI (Resistance)", alpha=0.9)
        bars_pe = ax_oi.bar(x_indices + bar_w/2, pe_oi, width=bar_w, color=self.pe_color, label="Put OI (Support)", alpha=0.9)

        ax_oi.set_xticks(x_indices)
        ax_oi.set_xticklabels([f"{int(s)}" for s in strikes], rotation=30)
        ax_oi.set_ylabel("Open Interest (Lakh Contracts)", color=self.text_muted, fontsize=11)
        ax_oi.set_title("Cumulative Open Interest Distribution by Strike", color=self.text_main, fontsize=13, weight="bold", pad=10)
        ax_oi.grid(color=self.border_color, linestyle="--", linewidth=0.6, alpha=0.7, axis="y")
        ax_oi.legend(facecolor=self.panel_color, edgecolor=self.border_color, labelcolor=self.text_main, loc="upper right")

        # Highlight Spot Price & Max Pain on plot
        spot_idx = np.argmin(np.abs(np.array(strikes) - spot))
        pain_idx = np.argmin(np.abs(np.array(strikes) - max_pain))
        ax_oi.axvline(spot_idx, color=self.spot_color, linestyle="--", linewidth=2.0, label=f"Spot ~ {spot:.0f}")
        ax_oi.axvline(pain_idx, color=self.pain_color, linestyle=":", linewidth=2.0, label=f"Max Pain ~ {max_pain:.0f}")

        # ----------------- Panel 2: Change in OI (Fresh Writing vs Unwinding) -----------------
        ax_chg = fig.add_subplot(gs[2, :])
        ax_chg.set_facecolor(self.panel_color)
        ax_chg.spines["bottom"].set_color(self.border_color)
        ax_chg.spines["top"].set_color(self.border_color)
        ax_chg.spines["left"].set_color(self.border_color)
        ax_chg.spines["right"].set_color(self.border_color)
        ax_chg.tick_params(colors=self.text_muted, labelsize=10)

        ax_chg.bar(x_indices - bar_w/2, ce_chg, width=bar_w, color=self.ce_color, label="Call Chg OI (Call Writing / Unwinding)", alpha=0.85)
        ax_chg.bar(x_indices + bar_w/2, pe_chg, width=bar_w, color=self.pe_color, label="Put Chg OI (Put Writing / Unwinding)", alpha=0.85)

        ax_chg.axhline(0, color=self.text_muted, linewidth=1.0)
        ax_chg.set_xticks(x_indices)
        ax_chg.set_xticklabels([f"{int(s)}" for s in strikes], rotation=30)
        ax_chg.set_ylabel("Change in OI (Lakh Contracts)", color=self.text_muted, fontsize=11)
        ax_chg.set_title("Intraday Net Additions / Unwinding (Where Market Makers Positioned Today)", color=self.text_main, fontsize=13, weight="bold", pad=10)
        ax_chg.grid(color=self.border_color, linestyle="--", linewidth=0.6, alpha=0.7, axis="y")
        ax_chg.legend(facecolor=self.panel_color, edgecolor=self.border_color, labelcolor=self.text_main, loc="upper right")

        # Save to reports and docs
        report_path = REPORTS_DIR / filename
        docs_path = DOCS_DIR / filename

        plt.savefig(report_path, dpi=160, bbox_inches="tight", facecolor=self.bg_color)
        plt.savefig(docs_path, dpi=160, bbox_inches="tight", facecolor=self.bg_color)
        plt.close(fig)

        return report_path
