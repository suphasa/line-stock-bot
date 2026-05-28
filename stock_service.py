"""
股票資料服務
台股：優先使用 TWSE 即時 API，備援使用 yfinance
美股：使用 yfinance
"""

import re
import logging
import requests
import yfinance as yf
from functools import lru_cache
from datetime import datetime, date

logger = logging.getLogger(__name__)

# TWSE 即時報價 API（上市股票）
TWSE_REALTIME_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
# TWSE 個股基本資料
TWSE_COMPANY_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
# 上櫃股票（OTC）即時 API
TPEX_REALTIME_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_realtime_quotes"

# 台股公司名稱快取（避免重複請求）
_TW_COMPANY_CACHE: dict[str, str] = {}


# ── 主要介面 ───────────────────────────────────────────────────────────────────

def get_stock_info(code: str, market: str) -> dict | None:
    """
    取得股票即時資料，統一格式回傳。

    Args:
        code:   股票代碼（台股：'2330'；美股：'AAPL'）
        market: 'TW' 或 'US'

    Returns:
        統一格式的 dict，或 None（代碼不存在）
    """
    if market == "TW":
        return _get_tw_stock(code)
    elif market == "US":
        return _get_us_stock(code)
    else:
        raise ValueError(f"不支援的市場：{market}")


# ── 台股 ───────────────────────────────────────────────────────────────────────

def _get_tw_stock(code: str) -> dict | None:
    """台股：優先 TWSE 即時 API，失敗則 fallback 到 yfinance"""
    # 先嘗試上市（TSE）
    data = _twse_realtime(code, exchange="tse")
    if data:
        return data

    # 再嘗試上櫃（OTC）
    data = _twse_realtime(code, exchange="otc")
    if data:
        return data

    # Fallback：yfinance（含歷史資料）
    logger.warning(f"TWSE API 失敗，改用 yfinance 查詢 {code}.TW")
    return _yfinance_stock(code + ".TW", market="TW", original_code=code)


def _twse_realtime(code: str, exchange: str = "tse") -> dict | None:
    """
    呼叫 TWSE 即時報價 API
    exchange: 'tse'（上市）或 'otc'（上櫃）
    """
    try:
        ex_ch = f"{exchange}_{code}.tw"
        resp = requests.get(
            TWSE_REALTIME_URL,
            params={"ex_ch": ex_ch, "json": "1", "delay": "0"},
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        json_data = resp.json()

        items = json_data.get("msgArray", [])
        if not items:
            return None

        item = items[0]

        # TWSE 回傳欄位說明：
        # z = 當盤成交價, y = 昨收, o = 開盤, h = 最高, l = 最低
        # v = 成交量(張), n = 公司名稱, c = 代碼
        current_price = _safe_float(item.get("z") or item.get("y"))
        if current_price is None:
            return None

        prev_close = _safe_float(item.get("y"))
        open_price = _safe_float(item.get("o"))
        high = _safe_float(item.get("h"))
        low = _safe_float(item.get("l"))
        volume_lots = _safe_float(item.get("v"))  # 張（1張=1000股）
        name = item.get("n", code)

        change = round(current_price - prev_close, 2) if prev_close else 0
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0

        return {
            "code": code,
            "name": name,
            "market": "TW",
            "exchange": "上市" if exchange == "tse" else "上櫃",
            "price": current_price,
            "prev_close": prev_close,
            "open": open_price,
            "high": high,
            "low": low,
            "change": change,
            "change_pct": change_pct,
            "volume": int(volume_lots) if volume_lots else None,
            "volume_unit": "張",
            "currency": "TWD",
            "pe_ratio": None,        # TWSE 即時 API 不含 PE，可用 FinMind 補充
            "market_cap": None,
            "52w_high": None,
            "52w_low": None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": "TWSE",
        }

    except requests.RequestException as e:
        logger.warning(f"TWSE API 請求失敗（{exchange} {code}）: {e}")
        return None
    except Exception as e:
        logger.warning(f"TWSE 資料解析失敗（{code}）: {e}")
        return None


# ── 美股 ────────────────────────────────────────────────────────────────────

def _get_us_stock(code: str) -> dict | None:
    """美股：使用 yfinance"""
    return _yfinance_stock(code, market="US", original_code=code)


# ── yfinance 通用 ────────────────────────────────────────────────────────────────

def _yfinance_stock(ticker_symbol: str, market: str, original_code: str) -> dict | None:
    """
    使用 yfinance 取得股票資料（台股加 .TW 後綴，美股直接代碼）
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info

        # 確認股票存在（yfinance 對不存在的代碼回傳空 dict 或僅有少數欄位）
        if not info or info.get("regularMarketPrice") is None:
            # 嘗試從 history 判斷
            hist = ticker.history(period="1d")
            if hist.empty:
                return None
            current_price = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Open"].iloc[-1])
        else:
            current_price = info.get("regularMarketPrice") or info.get("currentPrice")
            prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")

        if not current_price:
            return None

        prev_close = prev_close or current_price
        change = round(current_price - prev_close, 2)
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0

        # 判斷幣別
        currency = info.get("currency", "TWD" if market == "TW" else "USD")

        # 市值單位轉換
        market_cap_raw = info.get("marketCap")
        market_cap_str = _format_market_cap(market_cap_raw, currency)

        return {
            "code": original_code,
            "name": info.get("shortName") or info.get("longName") or original_code,
            "market": market,
            "exchange": info.get("exchange", ""),
            "price": round(current_price, 2),
            "prev_close": round(prev_close, 2),
            "open": round(info.get("regularMarketOpen", 0) or 0, 2),
            "high": round(info.get("regularMarketDayHigh", 0) or 0, 2),
            "low": round(info.get("regularMarketDayLow", 0) or 0, 2),
            "change": change,
            "change_pct": change_pct,
            "volume": info.get("regularMarketVolume"),
            "volume_unit": "股",
            "currency": currency,
            "pe_ratio": _safe_round(info.get("trailingPE")),
            "market_cap": market_cap_str,
            "52w_high": _safe_round(info.get("fiftyTwoWeekHigh")),
            "52w_low": _safe_round(info.get("fiftyTwoWeekLow")),
            "eps": _safe_round(info.get("trailingEps")),
            "dividend_yield": _safe_round(
                (info.get("dividendYield") or 0) * 100, ndigits=2
            ),
            "sector": info.get("sector", ""),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": "yfinance",
        }

    except Exception as e:
        logger.error(f"yfinance 查詢失敗 {ticker_symbol}: {e}")
        return None


# ── 工具函式 ────────────────────────────────────────────────────────────────────

def _safe_float(value) -> float | None:
    """安全轉換字串為 float，忽略 '-' 或空值"""
    if value is None or value == "-" or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _safe_round(value, ndigits: int = 2):
    """安全四捨五入，None 回傳 None"""
    if value is None:
        return None
    try:
        return round(float(value), ndigits)
    except (ValueError, TypeError):
        return None


def _format_market_cap(raw: int | None, currency: str) -> str | None:
    """格式化市值"""
    if not raw:
        return None
    if currency == "TWD":
        # 台幣：億元
        yi = raw / 1e8
        return f"{yi:,.0f} 億"
    else:
        # 美元：B/T
        if raw >= 1e12:
            return f"${raw/1e12:.2f}T"
        elif raw >= 1e9:
            return f"${raw/1e9:.1f}B"
        else:
            return f"${raw/1e6:.0f}M"
