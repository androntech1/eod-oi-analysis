from typing import Dict, List, Optional, Any, Tuple
import math
from .config import ATM_STRIKE_WINDOW, SYMBOLS_CONFIG

class OIAnalyzer:
    """Quantitative Open Interest analyzer for NSE Option Chain data."""

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

        # Calculate Max Pain
        max_pain_strike = self._calculate_max_pain(parsed_strikes)

        # Support & Resistance levels
        sr_levels = self._extract_sr_levels(parsed_strikes, underlying_price)

        # Filter window around ATM
        atm_window_strikes = [
            s for s in parsed_strikes
            if abs(s["strikePrice"] - atm_strike) <= (ATM_STRIKE_WINDOW * self.strike_step)
        ]

        # Put-Call Ratios
        pcr_oi = round(tot_pe_oi / tot_ce_oi, 3) if tot_ce_oi > 0 else 1.0
        pcr_vol = round(tot_pe_vol / tot_ce_vol, 3) if tot_ce_vol > 0 else 1.0
        pcr_chg_oi = round(tot_pe_chg_oi / tot_ce_chg_oi, 3) if tot_ce_chg_oi != 0 else 1.0

        # Sentiment Assessment
        sentiment_info = self._evaluate_sentiment(
            underlying_price=underlying_price,
            max_pain=max_pain_strike,
            pcr_oi=pcr_oi,
            pcr_chg_oi=pcr_chg_oi,
            tot_ce_chg_oi=tot_ce_chg_oi,
            tot_pe_chg_oi=tot_pe_chg_oi,
            sr_levels=sr_levels,
            atm_strikes=atm_window_strikes,
            atm_strike=atm_strike
        )

        return {
            "symbol": self.symbol,
            "expiry": expiry,
            "timestamp": timestamp,
            "underlying_price": underlying_price,
            "atm_strike": atm_strike,
            "max_pain": max_pain_strike,
            "totals": {
                "ce_oi": tot_ce_oi,
                "pe_oi": tot_pe_oi,
                "ce_chg_oi": tot_ce_chg_oi,
                "pe_chg_oi": tot_pe_chg_oi,
                "ce_vol": tot_ce_vol,
                "pe_vol": tot_pe_vol,
                "pcr_oi": pcr_oi,
                "pcr_vol": pcr_vol,
                "pcr_chg_oi": pcr_chg_oi
            },
            "sr_levels": sr_levels,
            "sentiment": sentiment_info,
            "atm_window_strikes": atm_window_strikes,
            "all_strikes_count": len(parsed_strikes)
        }

    @staticmethod
    def _classify_buildup(price_change: float, oi_change: float, is_call: bool) -> str:
        """Classify derivative buildup based on price and OI change."""
        if oi_change > 0:
            if price_change > 0:
                return "Long Buildup" if is_call else "Put Buying (Bearish Spec)"
            else:
                return "Short Buildup (Call Writing)" if is_call else "Put Writing (Support Creation)"
        elif oi_change < 0:
            if price_change > 0:
                return "Short Covering (Bullish Push)" if is_call else "Put Short Covering"
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
                # Call payout if candidate > k
                if candidate > k:
                    total_loss += (candidate - k) * ce_oi
                # Put payout if candidate < k
                elif candidate < k:
                    total_loss += (k - candidate) * pe_oi

            if total_loss < min_loss:
                min_loss = total_loss
                best_strike = candidate

        return best_strike

    @staticmethod
    def _extract_sr_levels(strikes_data: List[Dict[str, Any]], spot: float) -> Dict[str, Any]:
        """Extract primary and dynamic Support & Resistance strikes."""
        # Top 2 Call OI strikes (Resistances)
        sorted_ce_oi = sorted(strikes_data, key=lambda x: x["ce_oi"], reverse=True)
        # Top 2 Put OI strikes (Supports)
        sorted_pe_oi = sorted(strikes_data, key=lambda x: x["pe_oi"], reverse=True)

        # Dynamic additions (Highest positive OI change today)
        sorted_ce_chg = sorted(strikes_data, key=lambda x: x["ce_chg_oi"], reverse=True)
        sorted_pe_chg = sorted(strikes_data, key=lambda x: x["pe_chg_oi"], reverse=True)

        # Unwinding (Most negative OI change)
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

    def _evaluate_sentiment(
        self,
        underlying_price: float,
        max_pain: float,
        pcr_oi: float,
        pcr_chg_oi: float,
        tot_ce_chg_oi: float,
        tot_pe_chg_oi: float,
        sr_levels: Dict[str, Any],
        atm_strikes: List[Dict[str, Any]],
        atm_strike: float
    ) -> Dict[str, Any]:
        """Compute composite sentiment score and market bias."""
        bull_points = 0
        bear_points = 0
        signals = []

        # 1. PCR OI Evaluation
        if pcr_oi >= 1.25:
            bull_points += 2
            signals.append(f"High PCR ({pcr_oi}): Heavy Put writing cushions downside (Bullish)")
        elif pcr_oi >= 1.05:
            bull_points += 1
            signals.append(f"Moderate PCR ({pcr_oi}): Mild bullish cushion")
        elif pcr_oi <= 0.75:
            bear_points += 2
            signals.append(f"Low PCR ({pcr_oi}): Heavy Call writing caps upside (Bearish)")
        elif pcr_oi <= 0.90:
            bear_points += 1
            signals.append(f"Sub-1 PCR ({pcr_oi}): Mild bearish overhang")
        else:
            signals.append(f"Neutral PCR ({pcr_oi}): Balanced Put/Call participation")

        # 2. Daily Change in OI (Fresh Writing bias)
        net_fresh_oi = tot_pe_chg_oi - tot_ce_chg_oi
        if pcr_chg_oi > 1.3 or (tot_pe_chg_oi > 0 and tot_ce_chg_oi < 0):
            bull_points += 2
            signals.append("Aggressive fresh Put writing over Calls today (Strong intraday bull support)")
        elif pcr_chg_oi < 0.75 or (tot_ce_chg_oi > 0 and tot_pe_chg_oi < 0):
            bear_points += 2
            signals.append("Heavy Call writing added today over Puts (Strong intraday bear resistance)")
        else:
            signals.append("Balanced intraday additions between Calls and Puts")

        # 3. Spot vs Max Pain
        pain_diff = underlying_price - max_pain
        if pain_diff > (self.strike_step * 1.5):
            bull_points += 1
            signals.append(f"Spot trading comfortably above Max Pain ({max_pain:.0f})")
        elif pain_diff < -(self.strike_step * 1.5):
            bear_points += 1
            signals.append(f"Spot trading below Max Pain ({max_pain:.0f})")

        # 4. ATM Strike writing distribution (±3 strikes)
        atm_focus = [s for s in atm_strikes if abs(s["strikePrice"] - atm_strike) <= (3 * self.strike_step)]
        atm_ce_chg = sum(s["ce_chg_oi"] for s in atm_focus)
        atm_pe_chg = sum(s["pe_chg_oi"] for s in atm_focus)
        if atm_pe_chg > atm_ce_chg * 1.25:
            bull_points += 1
            signals.append("ATM cluster shows dominant Put writing (Building higher floor)")
        elif atm_ce_chg > atm_pe_chg * 1.25:
            bear_points += 1
            signals.append("ATM cluster shows dominant Call writing (Pressure near spot)")

        # 5. Unwinding signals
        if sr_levels.get("max_call_unwinding_strike"):
            bull_points += 1
            signals.append(f"Call unwinding observed at strike {sr_levels['max_call_unwinding_strike']:.0f} (Shorts covering)")
        if sr_levels.get("max_put_unwinding_strike"):
            bear_points += 1
            signals.append(f"Put unwinding observed at strike {sr_levels['max_put_unwinding_strike']:.0f} (Longs/Puts giving up)")

        # Final Verdict Determination
        net_score = bull_points - bear_points
        if net_score >= 3:
            verdict = "STRONG_BULLISH"
            badge_color = "#10b981" # Green
        elif net_score in (1, 2):
            verdict = "MILD_BULLISH"
            badge_color = "#34d399" # Light green
        elif net_score in (-1, -2):
            verdict = "MILD_BEARISH"
            badge_color = "#f87171" # Light red
        elif net_score <= -3:
            verdict = "STRONG_BEARISH"
            badge_color = "#ef4444" # Red
        else:
            verdict = "NEUTRAL_RANGEBOUND"
            badge_color = "#fbbf24" # Yellow

        return {
            "verdict": verdict,
            "score": net_score,
            "badge_color": badge_color,
            "bull_points": bull_points,
            "bear_points": bear_points,
            "signals": signals
        }

    def detect_market_shift(
        self,
        current_summary: Dict[str, Any],
        previous_summary: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compare current EOD snapshot with previous day's snapshot to detect directional shifts.
        """
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

        prev_pcr = previous_summary.get("totals", {}).get("pcr_oi", 1.0)
        curr_pcr = current_summary.get("totals", {}).get("pcr_oi", 1.0)
        pcr_delta = round(curr_pcr - prev_pcr, 3)

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
        details.append(f"Spot Price: {prev_spot:.2f} -> {curr_spot:.2f} ({spot_change:+.2f} pts, {spot_change_pct:+.2f}%)")
        details.append(f"PCR (OI): {prev_pcr:.3f} -> {curr_pcr:.3f} ({pcr_delta:+.3f})")
        details.append(f"Max Pain: {prev_pain:.0f} -> {curr_pain:.0f} ({pain_shift:+.0f} pts)")
        details.append(f"Key Range: Support {curr_s1:.0f} (was {prev_s1:.0f}) | Resistance {curr_r1:.0f} (was {prev_r1:.0f})")

        # Determine Shift
        shift_status = "CONTINUATION"
        headline = ""

        if "BEARISH" in prev_verdict and "BULLISH" in curr_verdict:
            shift_status = "BULLISH_REVERSAL"
            headline = "⚡ MARKET DIRECTION SHIFT DETECTED: Bearish phase flipped to Bullish bias!"
        elif "BULLISH" in prev_verdict and "BEARISH" in curr_verdict:
            shift_status = "BEARISH_REVERSAL"
            headline = "⚠️ MARKET DIRECTION SHIFT DETECTED: Bullish momentum rejected into Bearish pressure!"
        elif "NEUTRAL" in prev_verdict and "BULLISH" in curr_verdict:
            shift_status = "BULLISH_BREAKOUT"
            headline = "🚀 BREAKOUT SHIFT: Consolidation resolved into Bullish trend!"
        elif "NEUTRAL" in prev_verdict and "BEARISH" in curr_verdict:
            shift_status = "BEARISH_BREAKDOWN"
            headline = "🔻 BREAKDOWN SHIFT: Rangebound trading surrendered to Bearish breakdown!"
        elif "BULLISH" in curr_verdict and spot_change >= 0:
            shift_status = "BULL_CONTINUATION"
            headline = "🟢 Bull Phase Continues: Put writers defending higher strikes with persistent demand."
        elif "BEARISH" in curr_verdict and spot_change <= 0:
            shift_status = "BEAR_CONTINUATION"
            headline = "🔴 Bear Phase Continues: Persistent Call writing capping any recovery attempts."
        else:
            shift_status = "CONSOLIDATION"
            headline = "⚖️ Market in Consolidation: Balanced participation without clear structural shift."

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
