# LINE Stock AI Bot - FastAPI + LINE Messaging API SDK v3
import os, re, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient, Configuration, MessagingApi,
    ReplyMessageRequest, TextMessage, FlexMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
from stock_service import get_stock_info
from ai_service import answer_question, analyze_stock_with_ai
from flex_templates import build_stock_card

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

MSG_WELCOME      = "\u6211\u662f\u60a8\u7684\u80a1\u7968AI\u5c08\u5bb6\uff01\U0001f916\n\n\u53ef\u4ee5\u5354\u52a9\u60a8\uff1a\n\U0001f4c8 \u53f0\u80a1\u67e5\u8a62\uff1a\u8f38\u51652330\u3001\u53f0\u7a4d\u96fb\n\U0001f30e \u7f8e\u80a1\u67e5\u8a62\uff1a\u8f38\u5165AAPL\u3001TSLA\u3001NVDA\n\U0001f9e0 AI\u5206\u6790\uff1a\u8f38\u5165\u300c\u5206\u67902330\u300d\n\u8acb\u8f38\u5165\u80a1\u7968\u4ee3\u865f\u6216\u554f\u984c\uff1a"
MSG_TW_NOT_FOUND = "\u627e\u4e0d\u5230\u53f0\u80a1\u4ee3\u865f\u300c{code}\u300d\n\u8acb\u78ba\u8a8d\u4ee3\u865f\uff08\u4f8b\uff1a2330\u3001\u53f0\u7a4d\u96fb\uff09"
MSG_US_NOT_FOUND = "\u627e\u4e0d\u5230\u7f8e\u80a1\u4ee3\u865f\u300c{code}\u300d\n\u8acb\u78ba\u8a8d\u4ee3\u865f\uff08AAPL/TSLA/NVDA\uff09"
MSG_FETCH_ERROR  = "\u7121\u6cd5\u53d6\u5f97{code}\u7684\u8cc7\u6599\uff0c\u8acb\u7a0d\u5f8c\u518d\u8a66"
MSG_AI_THINKING  = "\U0001f914 AI\u6b63\u5728\u5206\u6790{code}\uff0c\u8acb\u7a0d\u5019\u2026"
MSG_AI_ERROR     = "\u62b1\u6b49\uff0cAI\u5206\u6790\u66ab\u6642\u7121\u6cd5\u4f7f\u7528\uff0c\u8acb\u7a0d\u5f8c\u518d\u8a66"
MSG_QA_THINKING  = "\U0001f914 \u6b63\u5728\u601d\u8003\u60a8\u7684\u554f\u984c\u2026"
MSG_QA_ERROR     = "\u62b1\u6b49\uff0c\u76ee\u524d\u7121\u6cd5\u56de\u7b54\uff0c\u8acb\u7a0d\u5f8c\u518d\u8a66"

WELCOME_TRIGGERS = [
    "hi", "hello", "Hi", "Hello",
    "\u9078\u55ae", "\u8f38\u5165", "\u4f60\u597d",
    "\u8acb\u554f", "\u5e6b\u52a9", "help",
]
ANALYZE_PREFIX = "\u5206\u6790"

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LINE Stock AI Bot starting...")
    yield
    logger.info("LINE Stock AI Bot stopped.")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "ok", "service": "LINE Stock AI Bot"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")
    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return PlainTextResponse("OK")

def send_reply(reply_token: str, messages: list):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages,
        ))

def text_msg(text: str) -> TextMessage:
    return TextMessage(text=text)

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    user_text = event.message.text.strip()
    reply_token = event.reply_token

    if user_text in WELCOME_TRIGGERS:
        send_reply(reply_token, [text_msg(MSG_WELCOME)])
        return

    if user_text.startswith(ANALYZE_PREFIX):
        code = user_text[len(ANALYZE_PREFIX):].strip().upper()
        send_reply(reply_token, [text_msg(MSG_AI_THINKING.format(code=code))])
        try:
            result = analyze_stock_with_ai(code)
            send_reply(reply_token, [text_msg(result)])
        except Exception as e:
            logger.error("AI analyze error: %s", e)
            send_reply(reply_token, [text_msg(MSG_AI_ERROR)])
        return

    if re.match(r"^\d{4,6}$", user_text):
        code = user_text
        info = get_stock_info(code, market="TW")
        if info is None:
            send_reply(reply_token, [text_msg(MSG_TW_NOT_FOUND.format(code=code))])
            return
        if "error" in info:
            send_reply(reply_token, [text_msg(MSG_FETCH_ERROR.format(code=code))])
            return
        card = build_stock_card(info)
        send_reply(reply_token, [FlexMessage(alt_text=info.get("name", code), contents=card)])
        return

    if re.match(r"^[A-Za-z]{1,5}$", user_text):
        code = user_text.upper()
        info = get_stock_info(code, market="US")
        if info is None:
            send_reply(reply_token, [text_msg(MSG_US_NOT_FOUND.format(code=code))])
            return
        if "error" in info:
            send_reply(reply_token, [text_msg(MSG_FETCH_ERROR.format(code=code))])
            return
        card = build_stock_card(info)
        send_reply(reply_token, [FlexMessage(alt_text=info.get("name", code), contents=card)])
        return

    send_reply(reply_token, [text_msg(MSG_QA_THINKING)])
    try:
        answer = answer_question(user_text)
        send_reply(reply_token, [text_msg(answer)])
    except Exception as e:
        logger.error("QA error: %s", e)
        send_reply(reply_token, [text_msg(MSG_QA_ERROR)])
