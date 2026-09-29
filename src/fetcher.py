import time
import logging
from datetime import datetime
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
    """Robust NSE client using curl_cffi with Chrome impersonation."""

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
    def classify_expiries(expiry_dates: List[str]) -> Dict[str, Optional[str]]:
        """
        Classify expiry dates into:
        - current_weekly: Nearest upcoming expiry
        - next_weekly: Second upcoming expiry
        - current_monthly: Last expiry of the current active month
        - next_monthly: Last expiry of the following month
        """
        if not expiry_dates:
            return {
                "current_weekly": None,
                "next_weekly": None,
                "current_monthly": None,
                "next_monthly": None
            }

        parsed_dates = []
        for exp in expiry_dates:
            try:
                dt = datetime.strptime(exp.strip(), "%d-%b-%Y")
                parsed_dates.append((dt, exp.strip()))
            except ValueError:
                continue

        parsed_dates.sort(key=lambda x: x[0])
        if not parsed_dates:
            return {
                "current_weekly": None,
                "next_weekly": None,
                "current_monthly": None,
                "next_monthly": None
            }

        current_weekly = parsed_dates[0][1]
        next_weekly = parsed_dates[1][1] if len(parsed_dates) > 1 else None

        # Group by (year, month) to identify monthly expiries (last expiry in that month)
        month_groups: Dict[tuple, List[tuple]] = {}
        for dt, exp_str in parsed_dates:
            key = (dt.year, dt.month)
            month_groups.setdefault(key, []).append((dt, exp_str))

        sorted_months = sorted(month_groups.keys())
        current_monthly = month_groups[sorted_months[0]][-1][1] if sorted_months else None
        next_monthly = month_groups[sorted_months[1]][-1][1] if len(sorted_months) > 1 else None

        return {
            "current_weekly": current_weekly,
            "next_weekly": next_weekly,
            "current_monthly": current_monthly,
            "next_monthly": next_monthly
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

    def fetch_comprehensive_data(self, symbol: str = "NIFTY") -> Dict[str, Any]:
        """
        Fetch contract info, classify expiries, and fetch option chain for:
        - Current Weekly
        - Current Monthly
        and returns unified raw bundle.
        """
        contract_info = self.get_contract_info(symbol)
        raw_expiries = contract_info.get("expiryDates", [])
        classified = self.classify_expiries(raw_expiries)

        # Unique expiries to fetch
        expiries_to_fetch = {}
        for role in ["current_weekly", "current_monthly", "next_weekly"]:
            exp_date = classified.get(role)
            if exp_date and exp_date not in expiries_to_fetch:
                logger.info("Fetching option-chain-v3 for %s (%s)...", exp_date, role)
                time.sleep(0.5)  # Respectful pause
                expiries_to_fetch[exp_date] = self.get_option_chain_v3(symbol, exp_date)

        return {
            "symbol": symbol,
            "fetch_time": datetime.now().isoformat(),
            "contract_info": contract_info,
            "classified_expiries": classified,
            "option_chains": expiries_to_fetch
        }
