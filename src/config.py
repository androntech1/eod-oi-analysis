import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
HISTORY_FILE = DATA_DIR / "history.json"
REPORTS_DIR = BASE_DIR / "reports"
DOCS_DIR = BASE_DIR / "docs"

# Ensure directories exist
for path in [SNAPSHOT_DIR, REPORTS_DIR, DOCS_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# NSE Endpoints
NSE_BASE_URL = "https://www.nseindia.com"
NSE_OPTION_CHAIN_URL = "https://www.nseindia.com/option-chain"
NSE_CONTRACT_INFO_API = "https://www.nseindia.com/api/option-chain-contract-info?symbol={symbol}"
NSE_OPTION_CHAIN_V3_API = "https://www.nseindia.com/api/option-chain-v3?type={symbol_type}&symbol={symbol}&expiry={expiry}"

# Symbols mapping & strike steps
SYMBOLS_CONFIG = {
    "NIFTY": {
        "symbol_type": "Indices",
        "strike_step": 50,
        "lot_size": 25,
        "display_name": "NIFTY 50"
    },
    "BANKNIFTY": {
        "symbol_type": "Indices",
        "strike_step": 100,
        "lot_size": 15,
        "display_name": "NIFTY BANK"
    },
    "FINNIFTY": {
        "symbol_type": "Indices",
        "strike_step": 50,
        "lot_size": 25,
        "display_name": "NIFTY FINANCIAL SERVICES"
    }
}

# Request Headers to mimic Chrome desktop
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": NSE_OPTION_CHAIN_URL,
    "Sec-Ch-Ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin"
}

# Analysis Settings
ATM_STRIKE_WINDOW = 10  # Active battleground: ATM ± 10 strikes (filters out far OTM hedge skew)
REQUEST_TIMEOUT = 18
MAX_RETRIES = 3
RETRY_DELAY = 2.5
