"""
Claude AI 分析引擎

兩種使用情境：
1. answer_question(question)   — 純自然語言股票問答
2. analyze_stock_with_ai(data) — 結合即時股票資料做深度分析
"""

import os
import logging
import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Claude 客戶端 ────────────────────────────────────────────────────────────────
_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-opus-4-6"
MAX_TOKENS = 1024

# ── System Prompt ────────────────────────────────────────────────────────────────
EXPERT_SYSTEM_PROMPT = """你是一位專業的股票分析師，名叫「阿財」，專精台灣股市與美股。

## 你的特點
- 以繁體中文回答，語氣親切但專業
- 善用數據與比較說明問題
- 分析涵蓋技術面、基本面、籌碼面
- 回答精簡有重點（500字以內），不廢話

## 重要原則
- 絕對不提供明確的「買/賣」指令，而是提供「客觀分析與參考」
- 回答結尾必須加上：「⚠️ 以上為分析參考，非投資建議，投資有風險，請自行判斷。」
- 不確定的資訊不要猜測，直說「需要查詢最新資料才能確認」

## 回答格式
- 用 emoji 讓訊息更易讀（📈📉💡⚠️等）
- 重要數字加粗描述
- 適當分段，不要長篇大論
"""

ANALYSIS_SYSTEM_PROMPT = """你是一位專業的股票分析師「阿財」，現在收到了一支股票的即時資料。

請根據這些數據進行分析，格式如下：

📊 **{股票名稱} 快速分析**

**技術面**
（根據價格、漲跌幅、成交量判斷短期趨勢）

**基本面**
（根據本益比、殖利率等數據判斷評價）

**風險提示**
（列出2-3個需注意的風險點）

⚠️ 以上為分析參考，非投資建議，投資有風險，請自行判斷。

---
規則：
- 繁體中文，親切專業
- 全文 400 字以內
- 若某項資料為 None，跳過該項不提及
"""


# ── 公開介面 ────────────────────────────────────────────────────────────────────

def answer_question(question: str) -> str:
    """
    回答使用者的自然語言股票問題
    例：「台積電現在適合買嗎？」「什麼是本益比？」
    """
    logger.info(f"AI 問答：{question[:50]}...")

    try:
        message = _client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=EXPERT_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": question}
            ],
        )
        return message.content[0].text

    except anthropic.APIConnectionError:
        logger.error("Claude API 連線失敗")
        return "⚠️ AI 目前連線異常，請稍後再試。\n你可以直接輸入股票代碼查詢即時價格 📈"
    except anthropic.RateLimitError:
        logger.error("Claude API 超出速率限制")
        return "⚠️ AI 目前使用人數過多，請稍後再試 🙏"
    except Exception as e:
        logger.error(f"Claude API 未知錯誤: {e}")
        return "⚠️ AI 分析發生問題，請稍後再試"


def analyze_stock_with_ai(stock_data: dict, user_question: str = "") -> str:
    """
    結合即時股票資料，讓 Claude 進行深度分析

    Args:
        stock_data:    來自 stock_service 的統一格式 dict
        user_question: 使用者的額外問題（可空白）
    """
    logger.info(f"AI 股票分析：{stock_data.get('code')} {stock_data.get('name')}")

    # 組建資料摘要給 Claude
    data_summary = _format_stock_data_for_ai(stock_data)

    user_prompt = f"""以下是 {stock_data.get('name')}（{stock_data.get('code')}）的即時資料：

{data_summary}

{"使用者問題：" + user_question if user_question else "請提供這支股票的綜合分析。"}"""

    try:
        message = _client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )
        return message.content[0].text

    except Exception as e:
        logger.error(f"股票分析失敗 {stock_data.get('code')}: {e}")
        return "⚠️ AI 分析暫時無法使用，請稍後再試"


# ── 工具函式 ────────────────────────────────────────────────────────────────────

def _format_stock_data_for_ai(data: dict) -> str:
    """
    將股票 dict 格式化為易讀的文字，給 Claude 當上下文
    """
    lines = []
    market_label = "台股" if data.get("market") == "TW" else "美股"
    currency = data.get("currency", "")

    lines.append(f"市場：{market_label}（{data.get('exchange', '')}）")
    lines.append(f"幣別：{currency}")

    price = data.get("price")
    if price:
        lines.append(f"當前價格：{price:,} {currency}")

    change = data.get("change")
    change_pct = data.get("change_pct")
    if change is not None and change_pct is not None:
        arrow = "▲" if change >= 0 else "▼"
        lines.append(f"漲跌：{arrow} {abs(change)} ({change_pct:+.2f}%)")

    for label, key in [
        ("開盤", "open"), ("最高", "high"), ("最低", "low"), ("昨收", "prev_close")
    ]:
        val = data.get(key)
        if val:
            lines.append(f"{label}：{val:,}")

    volume = data.get("volume")
    vol_unit = data.get("volume_unit", "")
    if volume:
        lines.append(f"成交量：{volume:,} {vol_unit}")

    for label, key in [
        ("本益比 (PE)", "pe_ratio"),
        ("每股盈餘 (EPS)", "eps"),
        ("殖利率", "dividend_yield"),
        ("市值", "market_cap"),
        ("52週高點", "52w_high"),
        ("52週低點", "52w_low"),
        ("產業", "sector"),
    ]:
        val = data.get(key)
        if val is not None and val != "" and val != 0:
            suffix = "%" if "殖利率" in label else ""
            lines.append(f"{label}：{val}{suffix}")

    lines.append(f"資料時間：{data.get('updated_at', '')}")

    return "\n".join(lines)
