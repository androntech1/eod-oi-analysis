import argparse
import sys
import os
import logging
from datetime import datetime, date
from pathlib import Path

from src.fetcher import NSEFetcher
from src.analyzer import OIAnalyzer
from src.storage import StorageManager
from src.visualizer import OIVisualizer
from src.reporter import OIReporter
from src.config import SYMBOLS_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("main")

def print_history_table(symbol: str):
    """Display all saved historical sessions from data/history.json."""
    storage = StorageManager()
    history = storage.get_history(symbol, limit=30)
    if not history:
        print(f"\nNo historical data found for {symbol} yet. Run an analysis first.\n")
        return

    print("\n" + "="*84)
    print(f"  {symbol} HISTORICAL EOD OPEN INTEREST & SHIFT REGISTRY")
    print("="*84)
    print(f"{'Date':<12} | {'Spot Close':<11} | {'ATM PCR':<8} | {'Max Pain':<9} | {'Support':<8} | {'Resist':<8} | {'Regime':<20}")
    print("-" * 84)
    for h in history:
        d = h.get("date", "")
        spot = f"{h.get('underlying_price', 0):,.2f}"
        pcr = f"{h.get('atm_pcr_oi', 1.0):.2f}"
        pain = f"{h.get('max_pain', 0):,.0f}"
        s1 = f"{h.get('support_1', 0):,.0f}"
        r1 = f"{h.get('resistance_1', 0):,.0f}"
        regime = str(h.get('tactical_regime', 'N/A'))[:20]
        print(f"{d:<12} | {spot:<11} | {pcr:<8} | {pain:<9} | {s1:<8} | {r1:<8} | {regime:<20}")
    print("="*84 + "\n")

def print_comparison(symbol: str, date1: str, date2: str):
    """Print detailed side-by-side comparison between two dates."""
    storage = StorageManager()
    comp = storage.compare_sessions(symbol, date1, date2)
    if "error" in comp:
        print(f"\n[ERROR] {comp['error']}\n")
        return

    print("\n" + "="*72)
    print(f"  {symbol} DAY-OVER-DAY SHIFT COMPARISON: {date2} vs {date1}")
    print("="*72)
    print(f"  Spot Price       : {comp['spot_old']:,.2f} -> {comp['spot_new']:,.2f} ({comp['spot_change']:+.2f} pts, {comp['spot_change_pct']:+.2f}%)")
    print(f"  Actionable ATM PCR: {comp['atm_pcr_old']:.2f} -> {comp['atm_pcr_new']:.2f} (Delta: {comp['atm_pcr_delta']:+.2f})")
    print(f"  Max Pain Drift   : {comp['max_pain_old']:,.0f} -> {comp['max_pain_new']:,.0f} ({comp['max_pain_shift']:+.0f} pts)")
    print(f"  Support (S1)     : {comp['support_migration']}")
    print(f"  Resistance (R1)  : {comp['resistance_migration']}")
    print(f"  Regime Evolution : {comp['regime_old']} -> {comp['regime_new']}")
    print("="*72 + "\n")

def run(symbol: str = "NIFTY", date_str: str = None, impersonate: str = "chrome124", skip_chart: bool = False):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    logger.info("Starting NSE EOD OI Analysis for %s on %s...", symbol, date_str)

    # 1. Fetch live/EOD data from NSE with Rollover Intelligence
    fetcher = NSEFetcher(impersonate=impersonate)
    raw_bundle = fetcher.fetch_comprehensive_data(symbol=symbol, ref_date=target_date)

    classified_exp = raw_bundle.get("classified_expiries", {})
    active_weekly = classified_exp.get("active_weekly")
    active_monthly = classified_exp.get("active_monthly")
    is_expiry_day = classified_exp.get("is_expiry_day", False)
    chains = raw_bundle.get("option_chains", {})

    if is_expiry_day:
        logger.info("⚡ Today is Expiry Day (%s). Expiring contract settled at EOD.", classified_exp.get('expired_today'))
        logger.info("🚀 Active actionable contract for upcoming sessions automatically advanced to: %s", active_weekly)

    if not active_weekly or active_weekly not in chains:
        logger.error("Failed to acquire option chain data for %s", active_weekly)
        sys.exit(1)

    # 2. Analyze Option Chains
    analyzer = OIAnalyzer(symbol=symbol)
    weekly_analysis = analyzer.analyze_chain(chains[active_weekly], expiry=active_weekly)

    monthly_analysis = {}
    if active_monthly and active_monthly in chains:
        monthly_analysis = analyzer.analyze_chain(chains[active_monthly], expiry=active_monthly)
    else:
        monthly_analysis = weekly_analysis

    # 3. Detect Market Shift with Historical Snapshot
    storage = StorageManager()
    prev_summary = storage.get_previous_snapshot_summary(symbol=symbol, current_date_str=date_str)
    market_shift = analyzer.detect_market_shift(weekly_analysis, prev_summary)

    # Consolidate complete analysis bundle
    analysis_result = {
        "symbol": symbol,
        "date": date_str,
        "fetch_timestamp": raw_bundle.get("fetch_time"),
        "is_expiry_day": is_expiry_day,
        "expired_today": classified_exp.get("expired_today"),
        "weekly_analysis": weekly_analysis,
        "monthly_analysis": monthly_analysis,
        "market_shift": market_shift
    }

    # 4. Save EOD Snapshot & Update History
    saved_snapshot_path = storage.save_eod_snapshot(symbol, date_str, analysis_result)
    logger.info("EOD snapshot saved: %s", saved_snapshot_path)

    # 5. Generate Visual Charts
    history = storage.get_history(symbol, limit=15)
    if not skip_chart:
        visualizer = OIVisualizer()
        chart_path = visualizer.generate_chart(analysis_result, history=history, filename="latest_oi_chart.png")
        logger.info("Visual intelligence card generated: %s", chart_path)

    # 6. Generate Markdown & HTML Reports
    reporter = OIReporter()
    report_md = reporter.generate_markdown_report(analysis_result, date_str=date_str)
    html_dashboard = reporter.generate_html_dashboard(analysis_result, history=history)
    logger.info("Markdown report saved: %s", report_md)
    logger.info("HTML dashboard saved: %s", html_dashboard)

    # 7. Print CLI Summary
    reporter.print_cli_summary(analysis_result)

    # 8. Append to GitHub Step Summary if running in GitHub Actions
    github_step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if github_step_summary and os.path.exists(os.path.dirname(github_step_summary)):
        try:
            with open(report_md, "r", encoding="utf-8") as f:
                report_content = f.read()
            with open(github_step_summary, "a", encoding="utf-8") as f:
                f.write(report_content)
        except Exception as e:
            logger.warning("Could not write GITHUB_STEP_SUMMARY: %s", e)

    return analysis_result

def main():
    parser = argparse.ArgumentParser(description="NSE EOD Open Interest & Directional Shift Analyzer")
    parser.add_argument("--symbol", type=str, default="NIFTY", choices=list(SYMBOLS_CONFIG.keys()), help="Index symbol")
    parser.add_argument("--date", type=str, default=None, help="Trading date in YYYY-MM-DD (default: today)")
    parser.add_argument("--history", action="store_true", help="Print table of all past recorded EOD sessions")
    parser.add_argument("--compare", nargs=2, metavar=("DATE_NEW", "DATE_OLD"), help="Compare two historical dates side-by-side (e.g. --compare 2026-09-29 2026-09-28)")
    parser.add_argument("--impersonate", type=str, default="chrome124", help="curl_cffi impersonate target")
    parser.add_argument("--skip-chart", action="store_true", help="Skip matplotlib chart generation")
    args = parser.parse_args()

    if args.history:
        print_history_table(symbol=args.symbol)
        return

    if args.compare:
        print_comparison(symbol=args.symbol, date1=args.compare[0], date2=args.compare[1])
        return

    run(symbol=args.symbol, date_str=args.date, impersonate=args.impersonate, skip_chart=args.skip_chart)

if __name__ == "__main__":
    main()
