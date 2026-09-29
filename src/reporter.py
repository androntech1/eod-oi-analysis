import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from .config import REPORTS_DIR, DOCS_DIR

class OIReporter:
    """Generates Markdown reports, interactive HTML GitHub Pages dashboard, and CLI summaries."""

    def __init__(self):
        self.reports_dir = REPORTS_DIR
        self.docs_dir = DOCS_DIR

    def generate_markdown_report(self, analysis_result: Dict[str, Any], date_str: str) -> Path:
        """Generate comprehensive GitHub-flavored Markdown report."""
        weekly = analysis_result.get("weekly_analysis", {})
        monthly = analysis_result.get("monthly_analysis", {})
        shift = analysis_result.get("market_shift", {})

        symbol = weekly.get("symbol", "NIFTY")
        spot = weekly.get("underlying_price", 0.0)
        max_pain = weekly.get("max_pain", 0.0)
        pcr = weekly.get("totals", {}).get("pcr_oi", 1.0)
        pcr_chg = weekly.get("totals", {}).get("pcr_chg_oi", 1.0)
        verdict = weekly.get("sentiment", {}).get("verdict", "NEUTRAL")
        sr = weekly.get("sr_levels", {})

        md = []
        md.append(f"# 📊 {symbol} EOD Open Interest & Directional Shift Analysis")
        md.append(f"**Date:** `{date_str}` | **Market Timestamp:** `{weekly.get('timestamp')}` | **Weekly Expiry:** `{weekly.get('expiry')}` | **Monthly Expiry:** `{monthly.get('expiry')}`\n")

        # Directional Shift Banner
        shift_headline = shift.get("headline", "Market Analysis Active")
        md.append(f"> ### {shift_headline}\n")

        # Metric summary cards in table
        md.append("| Metric | Value | Interpretation |")
        md.append("| :--- | :--- | :--- |")
        md.append(f"| **Spot Price** | **`{spot:,.2f}`** | Underlying index closing level |")
        md.append(f"| **Max Pain** | **`{max_pain:,.0f}`** | Strike where option writers incur minimum aggregate loss |")
        md.append(f"| **Overall PCR (OI)** | **`{pcr:.2f}`** | {'> 1.2 Bullish' if pcr >= 1.2 else ('< 0.8 Bearish' if pcr <= 0.8 else 'Neutral balance')} |")
        md.append(f"| **Change in OI PCR** | **`{pcr_chg:.2f}`** | {'> 1.2 Fresh Put writing dominance' if pcr_chg >= 1.2 else ('< 0.8 Fresh Call writing dominance' if pcr_chg <= 0.8 else 'Balanced intraday additions')} |")
        md.append(f"| **Market Bias** | **`{verdict}`** | Weekly composite bias |")
        md.append(f"| **Support Levels** | **S1: `{sr.get('support_1'):,.0f}`** / S2: `{sr.get('support_2'):,.0f}` | Major Put concentration floors |")
        md.append(f"| **Resistance Levels** | **R1: `{sr.get('resistance_1'):,.0f}`** / R2: `{sr.get('resistance_2'):,.0f}` | Major Call concentration ceilings |\n")

        # Embedded Visual Chart
        md.append("## 📈 Visual Open Interest Distribution")
        md.append("![EOD OI Analysis Chart](latest_oi_chart.png)\n")

        # Signals Breakdown
        signals = weekly.get("sentiment", {}).get("signals", [])
        if signals:
            md.append("### 🔍 Derivative Signals Detected")
            for s in signals:
                md.append(f"- {s}")
            md.append("")

        # Day-over-Day Shift Metrics
        if shift.get("has_previous_data"):
            md.append("### 🔄 Day-over-Day Comparison")
            for d in shift.get("details", []):
                md.append(f"- {d}")
            md.append("")

        # Weekly vs Monthly Perspective
        m_pcr = monthly.get("totals", {}).get("pcr_oi", 1.0)
        m_verdict = monthly.get("sentiment", {}).get("verdict", "NEUTRAL")
        md.append("### 🗓️ Weekly vs Monthly Alignment")
        md.append(f"- **Weekly View ({weekly.get('expiry')}):** `{verdict}` (PCR: `{pcr:.2f}`)")
        md.append(f"- **Monthly View ({monthly.get('expiry')}):** `{m_verdict}` (PCR: `{m_pcr:.2f}`)")
        if verdict == m_verdict:
            md.append(f"- **Alignment:** Weekly and Monthly trends are **congruent ({verdict})**, strengthening high-conviction follow-through.")
        else:
            md.append(f"- **Alignment:** **Divergence detected** between weekly tactical sentiment (`{verdict}`) and monthly structural trend (`{m_verdict}`). Caution warranted near key inflection points.")
        md.append("")

        # Strike Table (ATM ± 8 strikes)
        atm_strike = weekly.get("atm_strike", spot)
        atm_window = weekly.get("atm_window_strikes", [])
        focused_strikes = [s for s in atm_window if abs(s["strikePrice"] - atm_strike) <= (8 * weekly.get("strike_step", 50))]
        focused_strikes.sort(key=lambda x: x["strikePrice"])

        md.append("### 🎯 Strike-by-Strike Buildup Table (ATM Focus)")
        md.append("| Call OI (L) | Call Chg (L) | Call Buildup | Strike | Put Buildup | Put Chg (L) | Put OI (L) |")
        md.append("| :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        for s in focused_strikes:
            strike = s["strikePrice"]
            is_atm = strike == atm_strike
            tag = " **(ATM)**" if is_atm else ""
            c_oi = f"{s['ce_oi']/100000:.2f}"
            c_chg = f"{s['ce_chg_oi']/100000:+.2f}"
            c_b = s["ce_buildup"]
            p_oi = f"{s['pe_oi']/100000:.2f}"
            p_chg = f"{s['pe_chg_oi']/100000:+.2f}"
            p_b = s["pe_buildup"]
            md.append(f"| {c_oi} | {c_chg} | {c_b} | **{strike:,.0f}**{tag} | {p_b} | {p_chg} | {p_oi} |")
        md.append("\n---\n*Auto-generated by EOD OI Analysis Engine with browser TLS impersonation via curl_cffi.*")

        content = "\n".join(md)

        # Save dated report and latest.md
        dated_path = self.reports_dir / f"EOD_OI_ANALYSIS_{date_str}.md"
        latest_path = self.reports_dir / "latest.md"

        with open(dated_path, "w", encoding="utf-8") as f:
            f.write(content)
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write(content)

        return dated_path

    def generate_html_dashboard(self, analysis_result: Dict[str, Any], history: List[Dict[str, Any]]) -> Path:
        """Create responsive GitHub Pages HTML dashboard in docs/index.html."""
        weekly = analysis_result.get("weekly_analysis", {})
        monthly = analysis_result.get("monthly_analysis", {})
        shift = analysis_result.get("market_shift", {})

        symbol = weekly.get("symbol", "NIFTY")
        spot = weekly.get("underlying_price", 0.0)
        max_pain = weekly.get("max_pain", 0.0)
        pcr = weekly.get("totals", {}).get("pcr_oi", 1.0)
        pcr_chg = weekly.get("totals", {}).get("pcr_chg_oi", 1.0)
        verdict = weekly.get("sentiment", {}).get("verdict", "NEUTRAL").replace("_", " ")
        badge_color = weekly.get("sentiment", {}).get("badge_color", "#fbbf24")
        shift_status = shift.get("shift_status", "ACTIVE")
        shift_headline = shift.get("headline", "Market direction analysis ready")
        sr = weekly.get("sr_levels", {})

        atm_strike = weekly.get("atm_strike", spot)
        atm_window = weekly.get("atm_window_strikes", [])
        focused_strikes = [s for s in atm_window if abs(s["strikePrice"] - atm_strike) <= (8 * 50)]
        focused_strikes.sort(key=lambda x: x["strikePrice"])

        # Strike rows
        strike_rows_html = []
        for s in focused_strikes:
            strike = s["strikePrice"]
            is_atm = strike == atm_strike
            row_class = "atm-row" if is_atm else ""
            badge_atm = '<span class="badge badge-atm">ATM</span>' if is_atm else ""
            c_oi = f"{s['ce_oi']/100000:.2f}"
            c_chg = f"{s['ce_chg_oi']/100000:+.2f}"
            c_chg_class = "text-danger" if s["ce_chg_oi"] > 0 else ("text-success" if s["ce_chg_oi"] < 0 else "")
            p_oi = f"{s['pe_oi']/100000:.2f}"
            p_chg = f"{s['pe_chg_oi']/100000:+.2f}"
            p_chg_class = "text-success" if s["pe_chg_oi"] > 0 else ("text-danger" if s["pe_chg_oi"] < 0 else "")

            strike_rows_html.append(f"""
            <tr class="{row_class}">
                <td>{c_oi}</td>
                <td class="{c_chg_class}">{c_chg}</td>
                <td><span class="badge badge-subtle">{s['ce_buildup']}</span></td>
                <td class="strike-val">{strike:,.0f} {badge_atm}</td>
                <td><span class="badge badge-subtle">{s['pe_buildup']}</span></td>
                <td class="{p_chg_class}">{p_chg}</td>
                <td>{p_oi}</td>
            </tr>
            """)

        # History rows
        hist_rows_html = []
        for h in reversed(history[-7:]):
            hist_rows_html.append(f"""
            <tr>
                <td>{h.get('date')}</td>
                <td><b>{h.get('underlying_price', 0):,.2f}</b></td>
                <td>{h.get('weekly_pcr_oi', 1.0):.2f}</td>
                <td>{h.get('weekly_max_pain', 0):,.0f}</td>
                <td>{h.get('weekly_support_1', 0):,.0f} - {h.get('weekly_resistance_1', 0):,.0f}</td>
                <td><span class="badge badge-subtle">{h.get('weekly_sentiment', 'N/A')}</span></td>
            </tr>
            """)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{symbol} EOD OI Analysis Dashboard</title>
    <style>
        :root {{
            --bg: #0b0f19;
            --surface: #111827;
            --surface-elevated: #1f2937;
            --border: #374151;
            --text: #f9fafb;
            --text-muted: #9ca3af;
            --accent: #38bdf8;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.5;
            padding: 24px;
        }}
        .container {{ max-width: 1300px; margin: 0 auto; }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }}
        h1 {{ font-size: 24px; font-weight: 700; }}
        .meta {{ color: var(--text-muted); font-size: 14px; margin-top: 4px; }}
        .banner {{
            background: linear-gradient(135deg, rgba(31, 41, 55, 0.9), rgba(17, 24, 39, 0.9));
            border-left: 4px solid {badge_color};
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 24px;
            font-size: 16px;
            font-weight: 600;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 18px;
        }}
        .card-label {{ font-size: 12px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.05em; }}
        .card-value {{ font-size: 26px; font-weight: 700; margin-top: 6px; }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-verdict {{ background: {badge_color}; color: #000; }}
        .badge-atm {{ background: var(--accent); color: #000; margin-left: 6px; }}
        .badge-subtle {{ background: var(--surface-elevated); color: var(--text-muted); font-size: 11px; }}
        .chart-box {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .chart-box img {{ max-width: 100%; height: auto; border-radius: 6px; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th, td {{
            padding: 10px 12px;
            text-align: center;
            border-bottom: 1px solid var(--border);
        }}
        th {{ background: var(--surface-elevated); color: var(--text-muted); font-weight: 600; }}
        tr:hover {{ background: rgba(255, 255, 255, 0.02); }}
        .atm-row {{ background: rgba(56, 189, 248, 0.12) !important; font-weight: 600; }}
        .strike-val {{ font-weight: 700; color: var(--text); }}
        .text-success {{ color: var(--success); font-weight: 600; }}
        .text-danger {{ color: var(--danger); font-weight: 600; }}
        footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 13px;
            margin-top: 36px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>📈 {symbol} EOD OI & Market Direction Dashboard</h1>
                <div class="meta">NSE Official API &bull; Weekly Expiry: {weekly.get('expiry')} &bull; Timestamp: {weekly.get('timestamp')}</div>
            </div>
            <div>
                <span class="badge badge-verdict">{verdict}</span>
            </div>
        </header>

        <div class="banner">
            {shift_headline}
        </div>

        <div class="grid">
            <div class="card">
                <div class="card-label">Spot Price</div>
                <div class="card-value" style="color: var(--accent);">{spot:,.2f}</div>
            </div>
            <div class="card">
                <div class="card-label">Max Pain</div>
                <div class="card-value" style="color: var(--warning);">{max_pain:,.0f}</div>
            </div>
            <div class="card">
                <div class="card-label">Overall PCR (OI)</div>
                <div class="card-value" style="color: {'var(--success)' if pcr >= 1.0 else 'var(--danger)'};">{pcr:.2f}</div>
            </div>
            <div class="card">
                <div class="card-label">Change in OI PCR</div>
                <div class="card-value" style="color: {'var(--success)' if pcr_chg >= 1.0 else 'var(--danger)'};">{pcr_chg:.2f}</div>
            </div>
            <div class="card">
                <div class="card-label">Key Range (S1 - R1)</div>
                <div class="card-value" style="font-size: 19px;">{sr.get('support_1', 0):,.0f} - {sr.get('resistance_1', 0):,.0f}</div>
            </div>
        </div>

        <div class="chart-box">
            <h3 style="margin-bottom: 16px; text-align: left;">📊 Open Interest & Build-up Analytics</h3>
            <img src="latest_oi_chart.png" alt="Open Interest Distribution Chart">
        </div>

        <div class="card" style="margin-bottom: 24px; overflow-x: auto;">
            <h3 style="margin-bottom: 16px;">🎯 Strike-by-Strike Buildup (ATM Window)</h3>
            <table>
                <thead>
                    <tr>
                        <th>Call OI (L)</th>
                        <th>Call Chg OI (L)</th>
                        <th>Call Buildup</th>
                        <th>Strike</th>
                        <th>Put Buildup</th>
                        <th>Put Chg OI (L)</th>
                        <th>Put OI (L)</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(strike_rows_html)}
                </tbody>
            </table>
        </div>

        <div class="card" style="margin-bottom: 24px; overflow-x: auto;">
            <h3 style="margin-bottom: 16px;">🗓️ Recent Historical Snapshots</h3>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Spot Close</th>
                        <th>PCR (OI)</th>
                        <th>Max Pain</th>
                        <th>Range (S1 - R1)</th>
                        <th>Verdict</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(hist_rows_html)}
                </tbody>
            </table>
        </div>

        <footer>
            Automated NSE EOD Open Interest Analyzer &bull; Hosted on GitHub Pages &bull; Powered by curl_cffi & Python
        </footer>
    </div>
</body>
</html>
"""
        html_file = self.docs_dir / "index.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return html_file

    def print_cli_summary(self, analysis_result: Dict[str, Any]) -> None:
        """Concise, high-impact terminal summary."""
        weekly = analysis_result.get("weekly_analysis", {})
        monthly = analysis_result.get("monthly_analysis", {})
        shift = analysis_result.get("market_shift", {})

        spot = weekly.get("underlying_price", 0.0)
        max_pain = weekly.get("max_pain", 0.0)
        pcr = weekly.get("totals", {}).get("pcr_oi", 1.0)
        pcr_chg = weekly.get("totals", {}).get("pcr_chg_oi", 1.0)
        verdict = weekly.get("sentiment", {}).get("verdict", "NEUTRAL")
        sr = weekly.get("sr_levels", {})

        print("\n" + "="*68)
        print(f"  {weekly.get('symbol')} EOD OPEN INTEREST & SHIFT ANALYSIS")
        print("="*68)
        print(f"  Market Timestamp : {weekly.get('timestamp')}")
        print(f"  Spot Price       : {spot:,.2f}")
        print(f"  Max Pain         : {max_pain:,.0f}")
        print(f"  PCR (Total OI)   : {pcr:.2f}")
        print(f"  PCR (Change OI)  : {pcr_chg:.2f}")
        print(f"  Support (S1/S2)  : {sr.get('support_1'):,.0f} / {sr.get('support_2'):,.0f}")
        print(f"  Resistance(R1/R2): {sr.get('resistance_1'):,.0f} / {sr.get('resistance_2'):,.0f}")
        print(f"  Weekly Verdict   : {verdict}")
        print(f"  Monthly Verdict  : {monthly.get('sentiment', {}).get('verdict')}")
        print(f"  Direction Shift  : {shift.get('headline')}")
        print("="*68 + "\n")
