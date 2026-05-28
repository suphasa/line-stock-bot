import anthropic
import os
import re
import logging

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 512

EXPERT_SYSTEM_PROMPT = (
    "你是一位專業的股票分析師，擅長台灣股市和美市分析。\n"
    "請用繁體中文回答。\n\n"
    "你能夠：\n"
    "1. 解釋股市行情和趨勢\n"
    "2. 分析個股基本面和技術面\n"
    "3. 解釋股市指標和術語\n"
    "4. 提供參考資訊（不構成投資建議）\n"
    "5. 分析總體經濟和產業趨勢\n\n"
    "請保持專業、客觀，並提醒用戶投資有風險。"
)

ANALYSIS_SYSTEM_PROMPT = (
    "你是一位專業的股票分析師。根據提供的股票資料，給出簡明專業的分析。\n\n"
    "分析內容包括：\n"
    "1. 目前價格和漲動分析\n"
    "2. 與歷史高低比較\n"
    "3. 短期趨勢判斷\n"
    "4. 風險提醒\n\n"
    "請用繁體中文回答，保持專業客觀。"
)

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def answer_question(question: str) -> str:
    try:
        client = _get_client()
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=EXPERT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": question}],
        )
        return message.content[0].text
    except Exception as e:
        logger.error("answer_question error: %s", e)
        raise


def analyze_stock_with_ai(code: str) -> str:
    from stock_service import get_stock_info

    if re.match(r"^\d{4,6}$", code):
        info = get_stock_info(code, market="TW")
    else:
        info = get_stock_info(code, market="US")

    if info is None:
        return "找不到股票代號「" + code + "」的資料"
    if "error" in info:
        return "無法取得「" + code + "」的資料，請稍後再試"

    name = info.get("name", code)
    price = info.get("price", "N/A")
    change = info.get("change", "N/A")
    change_pct = info.get("change_pct", "N/A")
    high_52w = info.get("high_52w", "N/A")
    low_52w = info.get("low_52w", "N/A")
    volume = info.get("volume", "N/A")

    prompt = (
        "請分析以下股票：\n"
        + "股票代號：" + code + "\n"
        + "名稱：" + str(name) + "\n"
        + "目前價格：" + str(price) + "\n"
        + "今日漲跌：" + str(change) + "（" + str(change_pct) + "）\n"
        + "52週最高：" + str(high_52w) + "\n"
        + "52週最低：" + str(low_52w) + "\n"
        + "成交量：" + str(volume) + "\n"
    )

    try:
        client = _get_client()
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as e:
        logger.error("analyze_stock_with_ai error: %s", e)
        raise
