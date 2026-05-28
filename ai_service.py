import os
import re
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)
MODEL = "gemini-1.5-flash"   # 免費額度最穩定

# ══════════════════════════════════════════════
# 七人專業短線投資團隊 — System Prompt
# ══════════════════════════════════════════════
TEAM_SYSTEM_PROMPT = (
    "你是一個專業短線投資團隊，由以下7位成員組成，每次討論都要進行正式盤後會議。\n\n"
    "成員：\n"
    "📊 大盤策略分析師：分析大盤趨勢、市場氛圍、多空環境\n"
    "🔍 題材研究員：挖掘熱門題材、產業消息、市場催化劑\n"
    "📈 技術分析師：解讀K線、均線、RSI、MACD、量價關係\n"
    "💰 籌碼分析師：分析主力動向、外資投信、融資融券變化\n"
    "🛡️ 風控主管：評估風險、止損機制、控制最大回撤\n"
    "⚡ 交易執行主管：規劃進場時機、停損點、目標價位\n"
    "🎯 總結決策官：整合各方意見，給出最終建議\n\n"
    "【工作流程】\n"
    "1. 各成員輪流發表意見（內部討論）\n"
    "2. 交叉檢查，確認無明顯矛盾\n"
    "3. 風控主管進行風險驗證\n"
    "4. 決策官整合給出最終結論\n\n"
    "【輸出格式 — 請嚴格遵守】\n"
    "━━ 盤後分析會議 ━━\n"
    "📊 大盤：[意見]\n"
    "🔍 題材：[意見]\n"
    "📈 技術：[意見]\n"
    "💰 籌碼：[意見]\n"
    "🛡️ 風控：[風險評估]\n"
    "⚡ 執行：[執行建議]\n"
    "━━━━━━━━━━━━━━\n"
    "🎯 決策官：[最終結論]\n\n"
    "【最高原則 — 交易室文化】\n"
    "✅ 正確、專業、謹慎、不馬虎\n"
    "✅ 不硬推、不為湊數推薦\n"
    "✅ 寧可錯過，也不要亂做\n"
    "✅ 寧可觀望，也不要高風險硬進場\n"
    "✅ 資金生存最優先：控制回撤 > 追求獲利\n"
    "✅ 若市場風險升高，主動建議降低部位\n\n"
    "請用繁體中文回答。"
)

ADVISOR_PROMPT = (
    "你是專業短線投資團隊的投資顧問，負責解答股市相關問題。"
    "回答要專業、準確、清晰，適度提示風險，不給出過於明確的買賣指令。"
    "請用繁體中文回答。"
)


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def _is_market_question(text: str) -> bool:
    keywords = [
        "大盤", "行情", "漲", "跌", "買", "賣", "進場", "出場", "停損",
        "操作", "策略", "趨勢", "布局", "今天", "明天", "這週", "下週",
        "機會", "風險", "倉位", "持股", "換股", "加碼", "減碼", "分析",
    ]
    return any(kw in text for kw in keywords)


def answer_question(question: str) -> str:
    client = _get_client()
    if _is_market_question(question):
        system = TEAM_SYSTEM_PROMPT
        prompt = f"請針對以下問題進行團隊討論：\n\n{question}"
    else:
        system = ADVISOR_PROMPT
        prompt = question

    response = client.models.generate_content(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=system),
        contents=prompt,
    )
    return response.text


def analyze_stock_with_ai(code: str) -> str:
    from stock_service import get_stock_info
    if re.match(r"^\d{4,6}$", code):
        info = get_stock_info(code, market="TW")
    else:
        info = get_stock_info(code.upper(), market="US")

    if "error" in info:
        return f"⚠️ 無法取得 {code} 的股票資料：{info['error']}"

    name = info.get("name", code)
    data_summary = (
        f"股票代號：{info.get('code', code)}\n"
        f"股票名稱：{name}\n"
        f"目前價格：{info.get('price', 'N/A')}\n"
        f"漲跌幅：{info.get('change_percent', 'N/A')}\n"
        f"成交量：{info.get('volume', 'N/A')}\n"
        f"52週最高：{info.get('high_52w', 'N/A')}\n"
        f"52週最低：{info.get('low_52w', 'N/A')}\n"
        f"本益比：{info.get('pe_ratio', 'N/A')}\n"
        f"市值：{info.get('market_cap', 'N/A')}\n"
    )

    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=TEAM_SYSTEM_PROMPT),
        contents=f"請針對以下股票進行盤後分析會議：\n\n{data_summary}",
    )
    return response.text
