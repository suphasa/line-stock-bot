# -*- coding: utf-8 -*-
"""
LINE Stock AI Bot
FastAPI + LINE Messaging API SDK v3

Features:
  - Taiwan stocks (4-6 digit code)  -> Stock price card (e.g. "2330", "0050")
  - US stocks (1-5 letter ticker)   -> Stock price card (e.g. "AAPL", "tsla")
  - Free text questions              -> Claude AI answer
"""

import os
import re
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv

from stock_service import get_stock_info
from ai_service import answer_question, analyze_stock_with_ai
from flex_templates import build_stock_card

# ── Environment Variables ──────────────────────────────────────────────────────
load_dotenv()

CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── LINE SDK Setup ─────────────────────────────────────────────────────────────
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


# ── FastAPI App ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 LINE 股票 AI Bot 啟動中...")
    yield
    logger.info("Bot 關閉")


app = FastAPI(title="LINE Stock AI Bot", lifespan=lifespan)


# ── Health Check (used by Render) ──────────────────────────────────────────────
@app.get("/")
def health_check():
    return {"status": "ok", "message": "LINE 股票 AI Bot 運行中 📈"}


# ── Webhook Handler ────────────────────────────────────────────────────────────
@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_text = body.decode("utf-8")

    logger.info(f"收到 Webhook，簽名: {signature[:10]}...")

    try:
        handler.handle(body_text, signature)
    except InvalidSignatureError:
        logger.warning("簽名驗證失敗！")
        raise HTTPException(status_code=400, detail="Invalid signature")

    return PlainTextResponse("OK")


# ── Message Router ─────────────────────────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    user_text = event.message.text.strip()
    user_id = event.source.user_id
    logger.info(f"用戶 {user_id[:8]}... 訊息: {user_text}")

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # Note: route_message is synchronous (avoid async timeout issues)
        reply_messages = route_message(user_text)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=reply_messages,
            )
        )


def route_message(user_text: str) -> list:
    """
    Route user input:
    - Taiwan stock (4-6 digits) -> Flex card + optional AI analysis
    - US stock (1-5 letters)    -> Flex card + optional AI analysis
    - Free text                 -> Claude AI Q&A
    Returns a list of LINE Message objects (max 5 items)
    """
    # 1. Taiwan stock: 4-6 digit code
    tw_match = re.match(r"^(\d{4,6})(\s+(.+))?$", user_text)
    if tw_match:
        code = tw_match.group(1)
        extra_cmd = tw_match.group(3)  # e.g. "2330 分析"
        return handle_tw_stock(code, extra_cmd)

    # 2. US stock: 1-5 letter ticker (uppercase or lowercase)
    us_match = re.match(r"^([A-Za-z]{1,5})(\s+(.+))?$", user_text)
    if us_match and user_text.replace(" ", "").isalpha():
        code = us_match.group(1).upper()
        extra_cmd = us_match.group(3)
        return handle_us_stock(code, extra_cmd)

    # 3. AI Q&A (any other free text)
    return handle_ai_qa(user_text)


def handle_tw_stock(code: str, extra_cmd: str | None) -> list:
    """Taiwan stock -> Flex Message card"""
    try:
        data = get_stock_info(code, market="TW")
        if not data:
            return [TextMessage(text=(
                f"❌ 找不到台股代號「{code}」\n"
                f"請確認代號是否正確（如：2330、0050）"
            ))]

        flex_content = build_stock_card(data)
        messages = [
            FlexMessage(
                alt_text=f"📈 {data['name']} ({data['code']}) ${data['price']}",
                contents=flex_content,
            )
        ]

        # If user requests AI analysis
        if extra_cmd and any(k in extra_cmd for k in ["分析", "建議", "看法", "預測"]):
            ai_text = analyze_stock_with_ai(data, extra_cmd)
            messages.append(TextMessage(text=ai_text))

        return messages

    except Exception as e:
        logger.error(f"台股查詢失敗 {code}: {e}")
        return [TextMessage(text=f"⚠️ 查詢台股 {code} 暫時失敗，請稍後再試")]


def handle_us_stock(code: str, extra_cmd: str | None) -> list:
    """US stock -> Flex Message card"""
    try:
        data = get_stock_info(code, market="US")
        if not data:
            return [TextMessage(text=(
                f"❌ 找不到美股代號「{code}」\n"
                f"請確認代號是否正確（如：AAPL、TSLA、NVDA）"
            ))]

        flex_content = build_stock_card(data)
        messages = [
            FlexMessage(
                alt_text=f"📈 {data['name']} ({data['code']}) ${data['price']}",
                contents=flex_content,
            )
        ]

        if extra_cmd and any(k in extra_cmd for k in ["分析", "建議", "看法", "worth"]):
            ai_text = analyze_stock_with_ai(data, extra_cmd)
            messages.append(TextMessage(text=ai_text))

        return messages

    except Exception as e:
        logger.error(f"美股查詢失敗 {code}: {e}")
        return [TextMessage(text=f"⚠️ 查詢美股 {code} 暫時失敗，請稍後再試")]


def handle_ai_qh(question: str) -> list:
    """Claude AI free Q&A"""
    try:
        answer = answer_question(question)
        return [TextMessage(text=answer)]
    except Exception as e:
        logger.error(f"AI 回答失敗: {e}")
        return [TextMessage(text=(
            "⚠️ AI 分析暫時無法使用，請稍後再試\n"
            "您也可以直接輸入股票代號查詢行情 📈"
        ))]
