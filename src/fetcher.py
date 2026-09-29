import time
import logging
from datetime import datetime, date
from curl_cffi import requests
from typing import Dict, List, Optional, Any

from .config import (
    NSE_OPTION_CHAIN_URL,
    NSE_CONTRACT_INFO_API,
    NSE_OPTION_CHAIN_V3_API,
    SYMBOLS_CONFIG,
    BROWSER_HEADERS,
    API_HEADERS,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY
)

logger = logging.getLogger(__name__)

class NSEFetcher:
    """Robust NSE client using curl_cffi with Chrome impersonation and Rollover Intelligence."""

    def __init__(self, impersonate: str = "chrome124"):
        self.impersonate = impersonate
        self.session: Optional[requests.Session] = None
        self._init_session()

    def _init_session(self) -> None:
        """Initialize session and establish cookies from NSE option-chain page."""
        self.session = requests.Session(impersonate=self.impersonate)
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(
                    NSE_OPTION_CHAIN_URL,
                    headers=BROWSER_HEADERS,
                    timeout=REQUEST_TIMEOUT
                )
                if resp.status_code == 200:
                    logger.info("NSE session initialized successfully with cookies: %s", list(self.session.cookies.keys()))
                    return
                logger.warning("Session init attempt %d returned HTTP %d", attempt, resp.status_code)
            except Exception as e:
                logger.warning("Session init attempt %d failed: %s", attempt, e)
            time.sleep(RETRY_DELAY * attempt)
        raise RuntimeError("Failed to establish session with NSE after multiple attempts.")

    def get_contract_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch active expiry dates and strike prices for the symbol."""
        url = NSE_CONTRACT_INFO_API.format(symbol=symbol)
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, headers=API_HEADERS, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    if "expiryDates" in data:
                        return data
                elif resp.status_code in (401, 403):
                    logger.info("Session expired or blocked (HTTP %d). Reinitializing session...", resp.status_code)
                    self._init_session()
            except Exception as e:
                logger.warning("Error fetching contract info (attempt %d): %s", attempt, e)
            time.sleep(RETRY_DELAY * attempt)
        raise RuntimeError(f"Failed to fetch contract info for {symbol}")

    @staticmethod
    def classify_expiries(expiry_dates: List[str], ref_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Classify expiry dates with Rollover Intelligence:
        On an expiry day at EOD, big players have already rolled over.
        Analyzing an expired contract for tomorrow's trade is useless.
        Therefore, if nearest expiry == today, the active actionable contract
        automatically advances to next weekly & next monthly.
        """
        if not ref_date:
            ref_date = date.today()

        if not expiry_dates:
            return {
                "active_weekly": None,
                "active_monthly": None,
                "expired_today": None,
                "is_expiry_day": False
            }

        parsed = []
        for exp in expiry_dates:
            try:
                dt = datetime.strptime(exp.strip(), "%d-%b-%Y").date()
                parsed.append((dt, exp.strip()))
            except ValueError:
                continue

        parsed.sort(key=lambda x: x[0])
        if not parsed:
            return {
                "active_weekly": None,
                "active_monthly": None,
                "expired_today": None,
                "is_expiry_day": False
            }

        # Filter out past expiries (< ref_date)
        future_or_today = [p for p in parsed if p[0] >= ref_date]
        if not future_or_today:
            future_or_today = parsed[-2:] # Fallback

        first_date, first_str = future_or_today[0]
        is_expiry_day = (first_date == ref_date)

        expired_today = None
        if is_expiry_day:
            expired_today = first_str
            # At EOD of expiry day, the contract for upcoming trading sessions is the NEXT weekly
            if len(future_or_today) > 1:
                active_weekly_date, active_weekly_str = future_or_today[1]
                remaining_for_monthly = future_or_today[1:]
            else:
                active_weekly_str = first_str
                remaining_for_monthly = future_or_today
        else:
            active_weekly_str = first_str
            remaining_for_monthly = future_or_today

        # Group remaining active expiries by month to find the next active monthly expiry
        month_groups: Dict[tuple, List[tuple]] = {}
        for dt, exp_str in remaining_for_monthly:
            key = (dt.year, dt.month)
            month_groups.setdefault(key, []).append((dt, exp_str))

        sorted_months = sorted(month_groups.keys())
        active_monthly_str = month_groups[sorted_months[0]][-1][1] if sorted_months else active_weekly_str

        return {
            "active_weekly": active_weekly_str,
            "active_monthly": active_monthly_str,
            "expired_today": expired_today,
            "is_expiry_day": is_expiry_day,
            "all_expiries": [p[1] for p in future_or_today[:6]]
        }

    def get_option_chain_v3(self, symbol: str, expiry: str) -> Dict[str, Any]:
        """Fetch option chain v3 data for a specific symbol and expiry date."""
        cfg = SYMBOLS_CONFIG.get(symbol, {"symbol_type": "Indices"})
        symbol_type = cfg.get("symbol_type", "Indices")
        url = NSE_OPTION_CHAIN_V3_API.format(
            symbol_type=symbol_type,
            symbol=symbol,
            expiry=expiry
        )
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, headers=API_HEADERS, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    if "filtered" in data and "records" in data:
                        return data
                elif resp.status_code in (401, 403):
                    logger.info("Session expired (HTTP %d). Reinitializing session...", resp.status_code)
                    self._init_session()
            except Exception as e:
                logger.warning("Error fetching option chain v3 for %s %s (attempt %d): %s", symbol, expiry, attempt, e)
            time.sleep(RETRY_DELAY * attempt)
        raise RuntimeError(f"Failed to fetch option chain v3 for {symbol} on {expiry}")

    def fetch_comprehensive_data(self, symbol: str = "NIFTY", ref_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Fetch contract info, classify expiries, and fetch option chain for:
        - Active Weekly Expiry (Actionable for tomorrow)
        - Active Monthly Expiry (Structural trend)
        - Expired Today (if expiry day, to capture closing settling values)
        """
        contract_info = self.get_contract_info(symbol)
        raw_expiries = contract_info.get("expiryDates", [])
        classified = self.classify_expiries(raw_expiries, ref_date=ref_date)

        expiries_to_fetch = {}
        for role in ["active_weekly", "active_monthly", "expired_today"]:
            exp_date = classified.get(role)
            if exp_date and exp_date not in expiries_to_fetch:
                logger.info("Fetching option-chain-v3 for %s (%s)...", exp_date, role)
                time.sleep(0.4)
                expiries_to_fetch[exp_date] = self.get_option_chain_v3(symbol, exp_date)

        return {
            "symbol": symbol,
            "fetch_time": datetime.now().isoformat(),
            "contract_info": contract_info,
            "classified_expiries": classified,
            "option_chains": expiries_to_fetch
        }
