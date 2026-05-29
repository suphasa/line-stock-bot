"""
股票資料服務
台股：優先使用 TWSE 即時 API，備援使用 yfinance
美股：使用 yfinance
"""

import re
import logging
import requests
import yfinance as yf
from datetime import datetime

logger = logging.getLogger(__name__)

# TWSE 即時報價 API（上市股票）
TWSE_REALTIME_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"

# ── 主要介面 ────────────────────────────────────────────────────────────────────

def get_stock_info(code: str, market: str) -> dict | None:
    """
    取得股票即時資料，統一格式回傳。

    Args:
        code: 股票代碼（台股：'2330'；美股：'AAPL'）
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

# ── 台股 ────────────────────────────────────────────────────────────────────────

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

    # Fallback：yfinance（全天候，含盤後歷史資料）
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

        # 修正 Bug：分別評估 z 和 y，避免 "-" 字串短路問題
        # z = 當盤成交價（盤後為 "-"）, y = 昨收
        current_price = _safe_float(item.get("z")) or _safe_float(item.get("y"))
        if current_price is None:
            return None

        prev_close = _safe_float(item.get("y"))
        open_price = _safe_float(item.get("o"))
        high = _safe_float(item.get("h"))
        low = _safe_float(item.get("l"))
        volume_lots = _safe_float(item.get("v"))  # 張
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
            "pe_ratio": None,
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

# ── 美股 ────────────────────────────────────────────────────────────────────────

def _get_us_stock(code: str) -> dict | None:
    """美股：使用 yfinance"""
    return _yfinance_stock(code, market="US", original_code=code)

# ── yfinance 通用 ────────────────────────────────────────────────────────────────

def _yfinance_stock(ticker_symbol: str, market: str, original_code: str) -> dict | None:
    """
    使用 yfinance 取得股票資料（台股加 .TW 後綴，美股直接代碼）
    支援新舊版 yfinance 欄位名稱
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info

        # 嘗試多個欄位名稱（yfinance API 欄位名稱因版本而異）
        current_price = (
            info.get("currentPrice") or
            info.get("regularMarketPrice") or
            info.get("navPrice")
        )
        prev_close = (
            info.get("previousClose") or
            info.get("regularMarketPreviousClose")
        )

        if not current_price:
            # 從歷史資料取最近收盤價
            hist = ticker.history(period="5d")
            if hist.empty:
                return None
            current_price = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current_price

        prev_close = prev_close or current_price
        change = round(float(current_price) - float(prev_close), 2)
        change_pct = round(change / float(prev_close) * 100, 2) if prev_close else 0

        # 判斷幣別
        currency = info.get("currency", "TWD" if market == "TW" else "USD")

        # 市值格式化
        market_cap_raw = info.get("marketCap")
        market_cap_str = _format_market_cap(market_cap_raw, currency)

        return {
            "code": original_code,
            "name": info.get("shortName") or info.get("longName") or original_code,
            "market": market,
            "exchange": info.get("exchange", ""),
            "price": round(float(current_price), 2),
            "prev_close": round(float(prev_close), 2),
            "open": _safe_round(info.get("regularMarketOpen") or info.get("open")),
            "high": _safe_round(info.get("regularMarketDayHigh") or info.get("dayHigh")),
            "low": _safe_round(info.get("regularMarketDayLow") or info.get("dayLow")),
            "change": change,
            "change_pct": change_pct,
            "volume": info.get("regularMarketVolume") or info.get("volume"),
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
    """格式化市值（避免 f-string 中直接使用 $ 符號）"""
    if not raw:
        return None
    if currency == "TWD":
        yi = raw / 1e8
        return f"{yi:,.0f} 億"
    else:
        if raw >= 1e12:
            return "$" + f"{raw/1e12:.2f}T"
        elif raw >= 1e9:
            return "$" + f"{raw/1e9:.1f}B"
        else:
            return "$" + f"{raw/1e6:.0f}M"
