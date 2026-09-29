import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .config import SNAPSHOT_DIR, HISTORY_FILE

class StorageManager:
    """Manages EOD snapshot persistence and historical time-series indexing."""

    def __init__(self):
        self.snapshot_dir = SNAPSHOT_DIR
        self.history_file = HISTORY_FILE
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        if not self.history_file.exists():
            self._save_history({})

    def _load_history(self) -> Dict[str, Any]:
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_history(self, history: Dict[str, Any]) -> None:
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    def save_eod_snapshot(self, symbol: str, date_str: str, analysis_result: Dict[str, Any]) -> Path:
        """Save detailed EOD snapshot for the symbol and trading date."""
        filepath = self.snapshot_dir / f"{date_str}_{symbol}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(analysis_result, f, indent=2)

        # Update historical registry
        weekly_summary = analysis_result.get("weekly_analysis", {})
        monthly_summary = analysis_result.get("monthly_analysis", {})

        history = self._load_history()
        symbol_history = history.setdefault(symbol, [])

        # Remove existing entry for the same date if re-running
        symbol_history = [item for item in symbol_history if item.get("date") != date_str]

        compact_entry = {
            "date": date_str,
            "timestamp": weekly_summary.get("timestamp"),
            "underlying_price": weekly_summary.get("underlying_price"),
            "weekly_expiry": weekly_summary.get("expiry"),
            "monthly_expiry": monthly_summary.get("expiry"),
            "weekly_pcr_oi": weekly_summary.get("totals", {}).get("pcr_oi"),
            "weekly_pcr_chg_oi": weekly_summary.get("totals", {}).get("pcr_chg_oi"),
            "weekly_max_pain": weekly_summary.get("max_pain"),
            "weekly_sentiment": weekly_summary.get("sentiment", {}).get("verdict"),
            "weekly_resistance_1": weekly_summary.get("sr_levels", {}).get("resistance_1"),
            "weekly_support_1": weekly_summary.get("sr_levels", {}).get("support_1"),
            "monthly_pcr_oi": monthly_summary.get("totals", {}).get("pcr_oi"),
            "monthly_sentiment": monthly_summary.get("sentiment", {}).get("verdict"),
            "market_verdict": analysis_result.get("market_shift", {}).get("shift_status")
        }

        symbol_history.append(compact_entry)
        # Sort by date
        symbol_history.sort(key=lambda x: x["date"])
        history[symbol] = symbol_history
        self._save_history(history)

        return filepath

    def get_previous_snapshot_summary(self, symbol: str, current_date_str: str) -> Optional[Dict[str, Any]]:
        """Retrieve the latest prior day snapshot summary for comparative analysis."""
        history = self._load_history()
        symbol_history = history.get(symbol, [])
        prior_entries = [e for e in symbol_history if e.get("date") < current_date_str]
        if not prior_entries:
            return None

        # Return the most recent past entry
        latest_past_date = prior_entries[-1]["date"]
        past_file = self.snapshot_dir / f"{latest_past_date}_{symbol}.json"
        if past_file.exists():
            try:
                with open(past_file, "r", encoding="utf-8") as f:
                    past_data = json.load(f)
                    return past_data.get("weekly_analysis")
            except Exception:
                pass
        return None

    def get_history(self, symbol: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Get past N days history."""
        history = self._load_history()
        return history.get(symbol, [])[-limit:]
