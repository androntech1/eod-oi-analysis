import argparse
import sys
import os
import logging
from datetime import datetime
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

def run(symbol: str = "NIFTY", date_str: str = None, impersonate: str = "chrome124", skip_chart: bool = False):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    logger.info("Starting NSE EOD OI Analysis for %s on %s...", symbol, date_str)

    # 1. Fetch live/EOD data from NSE
    fetcher = NSEFetcher(impersonate=impersonate)
    raw_bundle = fetcher.fetch_comprehensive_data(symbol=symbol)

    classified_exp = raw_bundle.get("classified_expiries", {})
    weekly_exp = classified_exp.get("current_weekly")
    monthly_exp = classified_exp.get("current_monthly")
    chains = raw_bundle.get("option_chains", {})

    if not weekly_exp or weekly_exp not in chains:
        logger.error("Failed to acquire weekly option chain data for %s", weekly_exp)
        sys.exit(1)

    # 2. Analyze Option Chains
    analyzer = OIAnalyzer(symbol=symbol)
    weekly_analysis = analyzer.analyze_chain(chains[weekly_exp], expiry=weekly_exp)

    monthly_analysis = {}
    if monthly_exp and monthly_exp in chains:
        monthly_analysis = analyzer.analyze_chain(chains[monthly_exp], expiry=monthly_exp)
    else:
        monthly_analysis = weekly_analysis  # Fallback if monthly matches weekly

    # 3. Detect Market Shift with Historical Snapshot
    storage = StorageManager()
    prev_summary = storage.get_previous_snapshot_summary(symbol=symbol, current_date_str=date_str)
    market_shift = analyzer.detect_market_shift(weekly_analysis, prev_summary)

    # Consolidate complete analysis bundle
    analysis_result = {
        "symbol": symbol,
        "date": date_str,
        "fetch_timestamp": raw_bundle.get("fetch_time"),
        "weekly_analysis": weekly_analysis,
        "monthly_analysis": monthly_analysis,
        "market_shift": market_shift
    }

    # 4. Save EOD Snapshot & Update History
    saved_snapshot_path = storage.save_eod_snapshot(symbol, date_str, analysis_result)
    logger.info("EOD snapshot saved: %s", saved_snapshot_path)

    # 5. Generate Visual Charts
    if not skip_chart:
        visualizer = OIVisualizer()
        chart_path = visualizer.generate_chart(analysis_result, filename="latest_oi_chart.png")
        logger.info("Visual chart generated: %s", chart_path)

    # 6. Generate Markdown & HTML Reports
    reporter = OIReporter()
    report_md = reporter.generate_markdown_report(analysis_result, date_str=date_str)
    history = storage.get_history(symbol, limit=15)
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
    parser.add_argument("--impersonate", type=str, default="chrome124", help="curl_cffi impersonate target")
    parser.add_argument("--skip-chart", action="store_true", help="Skip matplotlib chart generation")
    args = parser.parse_args()

    run(symbol=args.symbol, date_str=args.date, impersonate=args.impersonate, skip_chart=args.skip_chart)

if __name__ == "__main__":
    main()
