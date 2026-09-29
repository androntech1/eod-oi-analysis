from typing import Dict, List, Optional, Any, Tuple
import math
from .config import ATM_STRIKE_WINDOW, SYMBOLS_CONFIG

class OIAnalyzer:
    """Institutional-grade Quantitative OI Analyzer with Strategic Action Playbooks."""

    def __init__(self, symbol: str = "NIFTY"):
        self.symbol = symbol
        self.config = SYMBOLS_CONFIG.get(symbol, {"strike_step": 50})
        self.strike_step = self.config.get("strike_step", 50)

    def analyze_chain(self, raw_chain_data: Dict[str, Any], expiry: str) -> Dict[str, Any]:
        """Analyze a single option chain for a given expiry."""
        records = raw_chain_data.get("records", {})
        filtered = raw_chain_data.get("filtered", {})

        underlying_price = float(records.get("underlyingValue", 0.0))
        timestamp = records.get("timestamp", "")
        chain_rows = filtered.get("data", [])

        if not chain_rows or underlying_price == 0.0:
            return {"error": "Incomplete option chain data"}

        # Calculate ATM Strike
        atm_strike = round(underlying_price / self.strike_step) * self.strike_step

        # Parse strikes
        parsed_strikes = []
        tot_ce_oi = 0.0
        tot_pe_oi = 0.0
        tot_ce_chg_oi = 0.0
        tot_pe_chg_oi = 0.0
        tot_ce_vol = 0
        tot_pe_vol = 0

        atm_ce_ltp = 0.0
        atm_pe_ltp = 0.0

        for row in chain_rows:
            strike = float(row.get("strikePrice", 0))
            ce = row.get("CE", {})
            pe = row.get("PE", {})

            ce_oi = float(ce.get("openInterest", 0) or 0)
            pe_oi = float(pe.get("openInterest", 0) or 0)
            ce_chg_oi = float(ce.get("changeinOpenInterest", 0) or 0)
            pe_chg_oi = float(pe.get("changeinOpenInterest", 0) or 0)
            ce_vol = int(ce.get("totalTradedVolume", 0) or 0)
            pe_vol = int(pe.get("totalTradedVolume", 0) or 0)
            ce_ltp = float(ce.get("lastPrice", 0) or 0)
            pe_ltp = float(pe.get("lastPrice", 0) or 0)
            ce_chg = float(ce.get("change", 0) or 0)
            pe_chg = float(pe.get("change", 0) or 0)
            ce_iv = float(ce.get("impliedVolatility", 0) or 0)
            pe_iv = float(pe.get("impliedVolatility", 0) or 0)

            tot_ce_oi += ce_oi
            tot_pe_oi += pe_oi
            tot_ce_chg_oi += ce_chg_oi
            tot_pe_chg_oi += pe_chg_oi
            tot_ce_vol += ce_vol
            tot_pe_vol += pe_vol

            if strike == atm_strike:
                atm_ce_ltp = ce_ltp
                atm_pe_ltp = pe_ltp

            # Buildup tags
            ce_buildup = self._classify_buildup(ce_chg, ce_chg_oi, is_call=True)
            pe_buildup = self._classify_buildup(pe_chg, pe_chg_oi, is_call=False)

            parsed_strikes.append({
                "strikePrice": strike,
                "ce_oi": ce_oi,
                "ce_chg_oi": ce_chg_oi,
                "ce_vol": ce_vol,
                "ce_ltp": ce_ltp,
                "ce_chg": ce_chg,
                "ce_iv": ce_iv,
                "ce_buildup": ce_buildup,
                "pe_oi": pe_oi,
                "pe_chg_oi": pe_chg_oi,
                "pe_vol": pe_vol,
                "pe_ltp": pe_ltp,
                "pe_chg": pe_chg,
                "pe_iv": pe_iv,
                "pe_buildup": pe_buildup
            })

        parsed_strikes.sort(key=lambda x: x["strikePrice"])

        # Filter strictly actionable ATM Window (ATM ± 10 strikes)
        # to prevent far OTM retail / institutional hedge positions from skewing analysis
        atm_window_strikes = [
            s for s in parsed_strikes
            if abs(s["strikePrice"] - atm_strike) <= (ATM_STRIKE_WINDOW * self.strike_step)
        ]

        # Calculate ATM Window specific metrics (Smart Money Battleground)
        atm_ce_oi = sum(s["ce_oi"] for s in atm_window_strikes)
        atm_pe_oi = sum(s["pe_oi"] for s in atm_window_strikes)
        atm_ce_chg = sum(s["ce_chg_oi"] for s in atm_window_strikes)
        atm_pe_chg = sum(s["pe_chg_oi"] for s in atm_window_strikes)

        atm_pcr_oi = round(atm_pe_oi / atm_ce_oi, 2) if atm_ce_oi > 0 else 1.0
        atm_pcr_chg = round(atm_pe_chg / atm_ce_chg, 2) if atm_ce_chg != 0 else 1.0

        # Overall (Full Chain) PCR
        total_pcr_oi = round(tot_pe_oi / tot_ce_oi, 2) if tot_ce_oi > 0 else 1.0
        total_pcr_vol = round(tot_pe_vol / tot_ce_vol, 2) if tot_ce_vol > 0 else 1.0

        # ATM Straddle & Expected Expiry Range
        atm_straddle_premium = round(atm_ce_ltp + atm_pe_ltp, 1)
        expected_range_lower = round(atm_strike - atm_straddle_premium)
        expected_range_upper = round(atm_strike + atm_straddle_premium)

        # Calculate Max Pain
        max_pain_strike = self._calculate_max_pain(parsed_strikes)

        # Support & Resistance levels within actionable range
        sr_levels = self._extract_sr_levels(atm_window_strikes, underlying_price)

        # Generate Actionable Institutional Playbook & Trapped Writer Analysis
        playbook = self._generate_strategic_playbook(
            underlying_price=underlying_price,
            atm_strike=atm_strike,
            max_pain=max_pain_strike,
            atm_pcr_oi=atm_pcr_oi,
            atm_pcr_chg=atm_pcr_chg,
            sr_levels=sr_levels,
            atm_window_strikes=atm_window_strikes,
            expected_range=(expected_range_lower, expected_range_upper),
            atm_straddle=atm_straddle_premium
        )

        return {
            "symbol": self.symbol,
            "expiry": expiry,
            "timestamp": timestamp,
            "underlying_price": underlying_price,
            "atm_strike": atm_strike,
            "max_pain": max_pain_strike,
            "atm_straddle": {
                "premium": atm_straddle_premium,
                "range_lower": expected_range_lower,
                "range_upper": expected_range_upper
            },
            "totals": {
                "ce_oi": tot_ce_oi,
                "pe_oi": tot_pe_oi,
                "pcr_oi": total_pcr_oi,
                "pcr_vol": total_pcr_vol,
                "atm_ce_oi": atm_ce_oi,
                "atm_pe_oi": atm_pe_oi,
                "atm_pcr_oi": atm_pcr_oi,
                "atm_pcr_chg_oi": atm_pcr_chg,
                "pcr_chg_oi": atm_pcr_chg
            },
            "sr_levels": sr_levels,
            "sentiment": playbook["sentiment_meta"],
            "playbook": playbook,
            "atm_window_strikes": atm_window_strikes,
            "all_strikes_count": len(parsed_strikes)
        }

    @staticmethod
    def _classify_buildup(price_change: float, oi_change: float, is_call: bool) -> str:
        """Classify derivative buildup based on price and OI change."""
        if oi_change > 0:
            if price_change > 0:
                return "Long Buildup" if is_call else "Put Buying (Hedging)"
            else:
                return "Short Buildup (Call Writing)" if is_call else "Put Writing (Support Creation)"
        elif oi_change < 0:
            if price_change > 0:
                return "Short Covering (Bullish Squeeze)" if is_call else "Put Short Covering"
            else:
                return "Long Unwinding" if is_call else "Put Long Unwinding"
        return "Neutral"

    @staticmethod
    def _calculate_max_pain(strikes_data: List[Dict[str, Any]]) -> float:
        """Calculate strike price where option sellers face minimal payout loss."""
        min_loss = float("inf")
        best_strike = 0.0

        all_strikes = [s["strikePrice"] for s in strikes_data]
        for candidate in all_strikes:
            total_loss = 0.0
            for row in strikes_data:
                k = row["strikePrice"]
                ce_oi = row["ce_oi"]
                pe_oi = row["pe_oi"]
                if candidate > k:
                    total_loss += (candidate - k) * ce_oi
                elif candidate < k:
                    total_loss += (k - candidate) * pe_oi

            if total_loss < min_loss:
                min_loss = total_loss
                best_strike = candidate

        return best_strike

    @staticmethod
    def _extract_sr_levels(strikes_data: List[Dict[str, Any]], spot: float) -> Dict[str, Any]:
        """Extract primary and dynamic Support & Resistance strikes within active battleground."""
        sorted_ce_oi = sorted(strikes_data, key=lambda x: x["ce_oi"], reverse=True)
        sorted_pe_oi = sorted(strikes_data, key=lambda x: x["pe_oi"], reverse=True)

        sorted_ce_chg = sorted(strikes_data, key=lambda x: x["ce_chg_oi"], reverse=True)
        sorted_pe_chg = sorted(strikes_data, key=lambda x: x["pe_chg_oi"], reverse=True)

        sorted_ce_unwind = sorted(strikes_data, key=lambda x: x["ce_chg_oi"])
        sorted_pe_unwind = sorted(strikes_data, key=lambda x: x["pe_chg_oi"])

        return {
            "resistance_1": sorted_ce_oi[0]["strikePrice"] if sorted_ce_oi else spot,
            "resistance_1_oi": sorted_ce_oi[0]["ce_oi"] if sorted_ce_oi else 0,
            "resistance_2": sorted_ce_oi[1]["strikePrice"] if len(sorted_ce_oi) > 1 else spot,
            "resistance_2_oi": sorted_ce_oi[1]["ce_oi"] if len(sorted_ce_oi) > 1 else 0,
            "support_1": sorted_pe_oi[0]["strikePrice"] if sorted_pe_oi else spot,
            "support_1_oi": sorted_pe_oi[0]["pe_oi"] if sorted_pe_oi else 0,
            "support_2": sorted_pe_oi[1]["strikePrice"] if len(sorted_pe_oi) > 1 else spot,
            "support_2_oi": sorted_pe_oi[1]["pe_oi"] if len(sorted_pe_oi) > 1 else 0,
            "max_call_addition_strike": sorted_ce_chg[0]["strikePrice"] if sorted_ce_chg else spot,
            "max_call_addition_oi": sorted_ce_chg[0]["ce_chg_oi"] if sorted_ce_chg else 0,
            "max_put_addition_strike": sorted_pe_chg[0]["strikePrice"] if sorted_pe_chg else spot,
            "max_put_addition_oi": sorted_pe_chg[0]["pe_chg_oi"] if sorted_pe_chg else 0,
            "max_call_unwinding_strike": sorted_ce_unwind[0]["strikePrice"] if sorted_ce_unwind and sorted_ce_unwind[0]["ce_chg_oi"] < 0 else None,
            "max_put_unwinding_strike": sorted_pe_unwind[0]["strikePrice"] if sorted_pe_unwind and sorted_pe_unwind[0]["pe_chg_oi"] < 0 else None,
        }

    def _generate_strategic_playbook(
        self,
        underlying_price: float,
        atm_strike: float,
        max_pain: float,
        atm_pcr_oi: float,
        atm_pcr_chg: float,
        sr_levels: Dict[str, Any],
        atm_window_strikes: List[Dict[str, Any]],
        expected_range: Tuple[float, float],
        atm_straddle: float
    ) -> Dict[str, Any]:
        """Synthesize deep institutional insights, trapped writer zones, and trade setups."""
        r1 = sr_levels.get("resistance_1", atm_strike + 100)
        s1 = sr_levels.get("support_1", atm_strike - 100)
        max_ce_add_strike = sr_levels.get("max_call_addition_strike", r1)
        max_pe_add_strike = sr_levels.get("max_put_addition_strike", s1)

        # Trapped Writer Detection
        trapped_writers = []
        if underlying_price > max_ce_add_strike and sr_levels.get("max_call_addition_oi", 0) > 0:
            trapped_writers.append(f"Call writers trapped at {max_ce_add_strike:,.0f} (Spot is trading above fresh call addition). Short covering trigger active!")
        elif underlying_price < max_pe_add_strike and sr_levels.get("max_put_addition_oi", 0) > 0:
            trapped_writers.append(f"Put writers trapped at {max_pe_add_strike:,.0f} (Spot closed below fresh put addition). Long liquidation pressure elevated!")
        else:
            trapped_writers.append(f"Writers comfortable between Support {s1:,.0f} and Resistance {r1:,.0f}.")

        # Market Regime & Conviction
        if atm_pcr_oi >= 1.25 and atm_pcr_chg >= 1.2:
            regime = "STRONG_BULLISH_EXPANSION"
            regime_desc = "Aggressive Put writing advancing higher. Bulls in full control."
            color = "#10b981"
        elif atm_pcr_oi >= 1.05 and atm_pcr_chg >= 0.9:
            regime = "MILD_BULLISH_BIAS"
            regime_desc = "Support holding firm with steady Put writing. Buy on dips towards S1."
            color = "#34d399"
        elif atm_pcr_oi <= 0.75 and atm_pcr_chg <= 0.75:
            regime = "STRONG_BEARISH_EXPANSION"
            regime_desc = "Heavy Call writing advancing lower. Bears dominating overhead supply."
            color = "#ef4444"
        elif atm_pcr_oi <= 0.90 and atm_pcr_chg <= 1.0:
            regime = "MILD_BEARISH_PRESSURE"
            regime_desc = "Overhead Call supply capping upside rallies. Sell on rise near R1."
            color = "#f87171"
        else:
            regime = "RANGEBOUND_CONSOLIDATION"
            regime_desc = "Balanced two-way writing. Market trapped inside S1-R1 strangle corridor."
            color = "#f59e0b"

        # Actionable Triggers for next session
        bullish_trigger = f"Break & 15-min sustain above {r1:,.0f} -> Triggers Call short covering towards {r1 + (self.strike_step * 2):,.0f}"
        bearish_trigger = f"Break & 15-min sustain below {s1:,.0f} -> Triggers Put writer panic unwinding towards {s1 - (self.strike_step * 2):,.0f}"
        range_play = f"Range corridor: {s1:,.0f} - {r1:,.0f} (Expect mean reversion within this band until breakout occurs)"

        # Smart Money Footprint Summary (2-3 crisp sentences)
        smart_money_verdict = (
            f"Active battleground (ATM ±10) shows an actionable PCR of {atm_pcr_oi:.2f} (Chg PCR: {atm_pcr_chg:.2f}). "
            f"The primary ceiling is locked at {r1:,.0f} (Highest Call OI), while the major institutional floor sits at {s1:,.0f} (Highest Put OI). "
            f"ATM straddle indicates an expected expiration boundary between {expected_range[0]:,.0f} and {expected_range[1]:,.0f}."
        )

        return {
            "regime": regime,
            "regime_desc": regime_desc,
            "color": color,
            "line_in_the_sand": atm_strike,
            "smart_money_verdict": smart_money_verdict,
            "trapped_writers": trapped_writers,
            "bullish_trigger": bullish_trigger,
            "bearish_trigger": bearish_trigger,
            "range_play": range_play,
            "expected_range": f"{expected_range[0]:,.0f} - {expected_range[1]:,.0f}",
            "atm_straddle_pts": atm_straddle,
            "sentiment_meta": {
                "verdict": regime,
                "badge_color": color,
                "atm_pcr_oi": atm_pcr_oi,
                "atm_pcr_chg": atm_pcr_chg,
                "signals": [regime_desc] + trapped_writers
            }
        }

    def detect_market_shift(
        self,
        current_summary: Dict[str, Any],
        previous_summary: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compare current EOD snapshot with previous day's snapshot to detect structural shifts."""
        if not previous_summary:
            return {
                "has_previous_data": False,
                "shift_status": "FIRST_RECORDED_SNAPSHOT",
                "headline": "Baseline snapshot established. Day-over-day shift comparison available from next trading session.",
                "details": []
            }

        prev_spot = previous_summary.get("underlying_price", 0.0)
        curr_spot = current_summary.get("underlying_price", 0.0)
        spot_change = curr_spot - prev_spot
        spot_change_pct = (spot_change / prev_spot * 100) if prev_spot > 0 else 0.0

        prev_pcr = previous_summary.get("totals", {}).get("atm_pcr_oi", previous_summary.get("totals", {}).get("pcr_oi", 1.0))
        curr_pcr = current_summary.get("totals", {}).get("atm_pcr_oi", 1.0)
        pcr_delta = round(curr_pcr - prev_pcr, 2)

        prev_pain = previous_summary.get("max_pain", 0.0)
        curr_pain = current_summary.get("max_pain", 0.0)
        pain_shift = curr_pain - prev_pain

        prev_verdict = previous_summary.get("sentiment", {}).get("verdict", "NEUTRAL")
        curr_verdict = current_summary.get("sentiment", {}).get("verdict", "NEUTRAL")

        prev_r1 = previous_summary.get("sr_levels", {}).get("resistance_1", 0.0)
        curr_r1 = current_summary.get("sr_levels", {}).get("resistance_1", 0.0)
        prev_s1 = previous_summary.get("sr_levels", {}).get("support_1", 0.0)
        curr_s1 = current_summary.get("sr_levels", {}).get("support_1", 0.0)

        details = []
        details.append(f"Spot Close: {prev_spot:,.2f} -> {curr_spot:,.2f} ({spot_change:+.2f} pts, {spot_change_pct:+.2f}%)")
        details.append(f"Actionable ATM PCR: {prev_pcr:.2f} -> {curr_pcr:.2f} ({pcr_delta:+.2f})")
        details.append(f"Max Pain Drift: {prev_pain:,.0f} -> {curr_pain:,.0f} ({pain_shift:+.0f} pts)")
        details.append(f"Range Migration: Support {curr_s1:,.0f} (prev: {prev_s1:,.0f}) | Resistance {curr_r1:,.0f} (prev: {prev_r1:,.0f})")

        # Determine Shift
        shift_status = "CONTINUATION"
        headline = ""

        if "BEARISH" in prev_verdict and "BULLISH" in curr_verdict:
            shift_status = "BULLISH_REVERSAL"
            headline = "⚡ MARKET DIRECTION SHIFT DETECTED: Bearish phase flipped to Bullish accumulation!"
        elif "BULLISH" in prev_verdict and "BEARISH" in curr_verdict:
            shift_status = "BEARISH_REVERSAL"
            headline = "⚠️ MARKET DIRECTION SHIFT DETECTED: Bull run rejected into Bearish distribution!"
        elif "CONSOLIDATION" in prev_verdict and "BULLISH" in curr_verdict:
            shift_status = "BULLISH_BREAKOUT"
            headline = "🚀 BREAKOUT EXPANSION: Rangebound trading resolved into Bullish expansion!"
        elif "CONSOLIDATION" in prev_verdict and "BEARISH" in curr_verdict:
            shift_status = "BEARISH_BREAKDOWN"
            headline = "🔻 BREAKDOWN EXPANSION: Support gave way to aggressive Bearish selling!"
        elif "BULLISH" in curr_verdict and spot_change >= 0:
            shift_status = "BULL_CONTINUATION"
            headline = "🟢 Bull Phase Continues: Put writers stepping up to higher strikes."
        elif "BEARISH" in curr_verdict and spot_change <= 0:
            shift_status = "BEAR_CONTINUATION"
            headline = "🔴 Bear Phase Continues: Persistent Call additions capping rallies."
        else:
            shift_status = "RANGEBOUND_CONSOLIDATION"
            headline = "⚖️ Neutral Consolidation: Option writers pinning price inside S1-R1 corridor."

        return {
            "has_previous_data": True,
            "shift_status": shift_status,
            "headline": headline,
            "spot_change": spot_change,
            "spot_change_pct": round(spot_change_pct, 2),
            "pcr_delta": pcr_delta,
            "pain_shift": pain_shift,
            "prev_verdict": prev_verdict,
            "curr_verdict": curr_verdict,
            "details": details
        }
