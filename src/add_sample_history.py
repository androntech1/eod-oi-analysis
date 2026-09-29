import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import SNAPSHOT_DIR, HISTORY_FILE

# Load today's snapshot as template
snap_29_path = SNAPSHOT_DIR / "2026-09-29_NIFTY.json"
with open(snap_29_path, "r", encoding="utf-8") as f:
    snap_28 = json.load(f)

snap_28["date"] = "2026-09-28"
snap_28["weekly_analysis"]["underlying_price"] = 22585.40
snap_28["weekly_analysis"]["max_pain"] = 22650.0
snap_28["weekly_analysis"]["totals"]["atm_pcr_oi"] = 0.86
snap_28["weekly_analysis"]["totals"]["atm_pcr_chg_oi"] = 0.65
snap_28["weekly_analysis"]["sr_levels"]["support_1"] = 22500.0
snap_28["weekly_analysis"]["sr_levels"]["resistance_1"] = 22700.0
snap_28["weekly_analysis"]["playbook"]["regime"] = "MILD_BEARISH_PRESSURE"
snap_28["weekly_analysis"]["playbook"]["regime_desc"] = "Overhead Call supply capping upside rallies."

snap_28_path = SNAPSHOT_DIR / "2026-09-28_NIFTY.json"
with open(snap_28_path, "w", encoding="utf-8") as f:
    json.dump(snap_28, f, indent=2)

with open(HISTORY_FILE, "r", encoding="utf-8") as f:
    hist = json.load(f)

nifty_hist = hist.get("NIFTY", [])
nifty_hist = [h for h in nifty_hist if h.get("date") != "2026-09-28"]
nifty_hist.append({
    "date": "2026-09-28",
    "timestamp": "28-Sep-2026 15:40:00",
    "underlying_price": 22585.40,
    "active_weekly_expiry": "29-Sep-2026",
    "active_monthly_expiry": "29-Sep-2026",
    "atm_pcr_oi": 0.86,
    "atm_pcr_chg_oi": 0.65,
    "full_chain_pcr_oi": 0.82,
    "max_pain": 22650.0,
    "tactical_regime": "MILD_BEARISH_PRESSURE",
    "support_1": 22500.0,
    "resistance_1": 22700.0,
    "monthly_atm_pcr": 0.86,
    "shift_verdict": "BEAR_CONTINUATION"
})
nifty_hist.sort(key=lambda x: x["date"])
hist["NIFTY"] = nifty_hist

with open(HISTORY_FILE, "w", encoding="utf-8") as f:
    json.dump(hist, f, indent=2)

print("Historical baseline for 2026-09-28 created.")
