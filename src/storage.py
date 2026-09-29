import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .config import SNAPSHOT_DIR, HISTORY_FILE

class StorageManager:
    """Manages EOD snapshot persistence, historical timeseries indexing, and multi-day lookbacks."""

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
        playbook = weekly_summary.get("playbook", {})

        history = self._load_history()
        symbol_history = history.setdefault(symbol, [])

        # Remove existing entry for the same date if re-running
        symbol_history = [item for item in symbol_history if item.get("date") != date_str]

        compact_entry = {
            "date": date_str,
            "timestamp": weekly_summary.get("timestamp"),
            "underlying_price": weekly_summary.get("underlying_price"),
            "active_weekly_expiry": weekly_summary.get("expiry"),
            "active_monthly_expiry": monthly_summary.get("expiry"),
            "atm_pcr_oi": weekly_summary.get("totals", {}).get("atm_pcr_oi"),
            "atm_pcr_chg_oi": weekly_summary.get("totals", {}).get("atm_pcr_chg_oi"),
            "full_chain_pcr_oi": weekly_summary.get("totals", {}).get("pcr_oi"),
            "max_pain": weekly_summary.get("max_pain"),
            "tactical_regime": playbook.get("regime", "NEUTRAL"),
            "support_1": weekly_summary.get("sr_levels", {}).get("support_1"),
            "resistance_1": weekly_summary.get("sr_levels", {}).get("resistance_1"),
            "monthly_atm_pcr": monthly_summary.get("totals", {}).get("atm_pcr_oi"),
            "shift_verdict": analysis_result.get("market_shift", {}).get("shift_status")
        }

        symbol_history.append(compact_entry)
        symbol_history.sort(key=lambda x: x["date"])
        history[symbol] = symbol_history
        self._save_history(history)

        return filepath

    def get_snapshot(self, symbol: str, date_str: str) -> Optional[Dict[str, Any]]:
        """Retrieve full snapshot data for a specific date."""
        filepath = self.snapshot_dir / f"{date_str}_{symbol}.json"
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def get_previous_snapshot_summary(self, symbol: str, current_date_str: str) -> Optional[Dict[str, Any]]:
        """Retrieve the latest prior day snapshot summary for comparative analysis."""
        history = self._load_history()
        symbol_history = history.get(symbol, [])
        prior_entries = [e for e in symbol_history if e.get("date") < current_date_str]
        if not prior_entries:
            return None

        latest_past_date = prior_entries[-1]["date"]
        past_data = self.get_snapshot(symbol, latest_past_date)
        if past_data:
            return past_data.get("weekly_analysis")
        return None

    def get_history(self, symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get past N days history."""
        history = self._load_history()
        return history.get(symbol, [])[-limit:]

    def list_available_dates(self, symbol: str) -> List[str]:
        """List all dates with saved snapshots."""
        history = self._load_history()
        return [e["date"] for e in history.get(symbol, [])]

    def compare_sessions(self, symbol: str, date_newer: str, date_older: str) -> Dict[str, Any]:
        """Compare any two historical sessions side by side."""
        snap_new = self.get_snapshot(symbol, date_newer)
        snap_old = self.get_snapshot(symbol, date_older)

        if not snap_new or not snap_old:
            return {"error": f"One or both dates ({date_newer}, {date_older}) not found in data archive."}

        w_new = snap_new.get("weekly_analysis", {})
        w_old = snap_old.get("weekly_analysis", {})

        spot_new = w_new.get("underlying_price", 0.0)
        spot_old = w_old.get("underlying_price", 0.0)
        spot_chg = spot_new - spot_old
        spot_chg_pct = (spot_chg / spot_old * 100) if spot_old > 0 else 0.0

        pcr_new = w_new.get("totals", {}).get("atm_pcr_oi", 1.0)
        pcr_old = w_old.get("totals", {}).get("atm_pcr_oi", 1.0)

        pain_new = w_new.get("max_pain", 0.0)
        pain_old = w_old.get("max_pain", 0.0)

        r1_new = w_new.get("sr_levels", {}).get("resistance_1", 0.0)
        r1_old = w_old.get("sr_levels", {}).get("resistance_1", 0.0)
        s1_new = w_new.get("sr_levels", {}).get("support_1", 0.0)
        s1_old = w_old.get("sr_levels", {}).get("support_1", 0.0)

        return {
            "symbol": symbol,
            "date_newer": date_newer,
            "date_older": date_older,
            "spot_old": spot_old,
            "spot_new": spot_new,
            "spot_change": spot_chg,
            "spot_change_pct": round(spot_chg_pct, 2),
            "atm_pcr_old": pcr_old,
            "atm_pcr_new": pcr_new,
            "atm_pcr_delta": round(pcr_new - pcr_old, 2),
            "max_pain_old": pain_old,
            "max_pain_new": pain_new,
            "max_pain_shift": pain_new - pain_old,
            "support_migration": f"{s1_old:,.0f} -> {s1_new:,.0f}",
            "resistance_migration": f"{r1_old:,.0f} -> {r1_new:,.0f}",
            "regime_old": w_old.get("playbook", {}).get("regime", "N/A"),
            "regime_new": w_new.get("playbook", {}).get("regime", "N/A"),
        }
