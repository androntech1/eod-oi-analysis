"""Self-contained verification test for EOD OI Analysis pipeline."""
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.analyzer import OIAnalyzer
from src.storage import StorageManager
from src.config import SNAPSHOT_DIR

def test_pipeline():
    analyzer = OIAnalyzer(symbol="NIFTY")

    # 1. Test Max Pain & Buildup Logic with mock strike data
    mock_strikes = [
        {"strikePrice": 22600, "ce_oi": 50000, "pe_oi": 250000, "ce_chg_oi": -2000, "pe_chg_oi": 30000, "ce_chg": 10, "pe_chg": -15},
        {"strikePrice": 22700, "ce_oi": 150000, "pe_oi": 200000, "ce_chg_oi": 5000, "pe_chg_oi": 15000, "ce_chg": -5, "pe_chg": 5},
        {"strikePrice": 22800, "ce_oi": 300000, "pe_oi": 60000, "ce_chg_oi": 40000, "pe_chg_oi": -10000, "ce_chg": -20, "pe_chg": 25}
    ]

    max_pain = analyzer._calculate_max_pain(mock_strikes)
    assert max_pain in [22600, 22700, 22800], f"Invalid max pain: {max_pain}"

    # Buildup verification
    assert analyzer._classify_buildup(10, 5000, is_call=True) == "Long Buildup"
    assert analyzer._classify_buildup(-10, 5000, is_call=True) == "Short Buildup (Call Writing)"
    assert analyzer._classify_buildup(10, -5000, is_call=True) == "Short Covering (Bullish Squeeze)"

    # 2. Test Directional Shift Detection
    prev_summary = {
        "underlying_price": 22600.0,
        "max_pain": 22600.0,
        "totals": {"atm_pcr_oi": 0.75, "atm_pcr_chg_oi": 0.70},
        "sentiment": {"verdict": "STRONG_BEARISH"},
        "sr_levels": {"resistance_1": 22700, "support_1": 22500}
    }

    curr_summary = {
        "underlying_price": 22750.0,
        "max_pain": 22750.0,
        "totals": {"atm_pcr_oi": 1.25, "atm_pcr_chg_oi": 1.40},
        "sentiment": {"verdict": "STRONG_BULLISH"},
        "sr_levels": {"resistance_1": 22900, "support_1": 22700}
    }

    shift = analyzer.detect_market_shift(curr_summary, prev_summary)
    assert shift["shift_status"] == "BULLISH_REVERSAL", f"Expected BULLISH_REVERSAL, got {shift['shift_status']}"
    assert shift["pcr_delta"] == 0.5

    # 3. Test Storage Manager snapshot persistence
    storage = StorageManager()
    assert storage.snapshot_dir.exists(), "Snapshot directory does not exist"

    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY.")

if __name__ == "__main__":
    test_pipeline()
