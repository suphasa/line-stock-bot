# LINE Stock AI Bot - FastAPI + BackgroundTasks + Push API
import os, re, logging, asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient, Configuration, MessagingApi,
    PushMessageRequest, TextMessage, FlexMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
import httpx
from stock_service import get_stock_info
from ai_service import answer_question, analyze_stock_with_ai
from flex_templates import build_stock_card

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

# Render sets this automatically; fallback to localhost for local dev
SERVICE_URL = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:10000")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(CHANNEL_SECRET)

MSG_WELCOME = "我是您的股票AI專家！\n\n可以協助您：\n台股查詢：輸入2330、台積電\n美股查詢：輸入AAPL、TSLA、NVDA\nAI分析：輸入「分析2330」\n請輸入股票代號或問題："
MSG_TW_NOT_FOUND = "找不到台股代號「{code}」\n請確認代號（例：2330、台積電）"
MSG_US_NOT_FOUND = "找不到美股代號「{code}」\n請確認代號（AAPL/TSLA/NVDA）"
MSG_FETCH_ERROR = "無法取得{code}的資料，請稍後再試"
MSG_AI_ERROR = "抱歉，AI分析暫時無法使用，請稍後再試"
MSG_QA_ERROR = "抱歉，目前無法回答，請稍後再試"

WELCOME_TRIGGERS = [
    "hi", "hello", "Hi", "Hello",
    "選單", "輸入", "你好",
    "請問", "幫助", "help",
]
ANALYZE_PREFIX = "分析"

# ── 心跳任務：每 9 分鐘 ping 自己，防止 Render 免費版休眠 ──────────────────
async def keepalive():
    """Ping own /health every 9 min to prevent Render free-tier spin-down."""
    await asyncio.sleep(60)  # 等 1 分鐘讓服務完全啟動
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{SERVICE_URL}/health")
                logger.info("Keepalive ping OK: %s", resp.status_code)
        except Exception as e:
            logger.warning("Keepalive ping failed: %s", e)
        await asyncio.sleep(540)  # 9 分鐘

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LINE Stock AI Bot starting...")
    task = asyncio.create_task(keepalive())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("LINE Stock AI Bot stopped.")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "ok", "service": "LINE Stock AI Bot"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

def send_push(user_id: str, messages: list):
    """Push message to user - no reply token needed, never expires."""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.push_message(PushMessageRequest(
            to=user_id,
            messages=messages,
        ))

def text_msg(text: str) -> TextMessage:
    return TextMessage(text=text)

def process_message(user_id: str, user_text: str):
    """Process message in background thread, reply via Push API."""
    user_text = user_text.strip()
    logger.info("Processing message from %s: %s", user_id, user_text[:50])

    # 特殊指令：查詢自己的 LINE User ID
    if user_text in ["我的ID", "我的id", "myid", "my id", "ID", "id"]:
        send_push(user_id, [text_msg(f"您的 LINE User ID 是：\n{user_id}")])
        return

    if user_text in WELCOME_TRIGGERS:
        send_push(user_id, [text_msg(MSG_WELCOME)])
        return

    if user_text.startswith(ANALYZE_PREFIX):
        code = user_text[len(ANALYZE_PREFIX):].strip().upper()
        try:
            result = analyze_stock_with_ai(code)
            send_push(user_id, [text_msg(result)])
        except Exception as e:
            logger.error("AI analyze error: %s", e)
            send_push(user_id, [text_msg(MSG_AI_ERROR)])
        return

    if re.match(r"^\d{4,6}$", user_text):
        code = user_text
        info = get_stock_info(code, market="TW")
        if info is None:
            send_push(user_id, [text_msg(MSG_TW_NOT_FOUND.format(code=code))])
            return
        if "error" in info:
            send_push(user_id, [text_msg(MSG_FETCH_ERROR.format(code=code))])
            return
        card = build_stock_card(info)
        send_push(user_id, [FlexMessage(alt_text=info.get("name", code), contents=card)])
        return

    if re.match(r"^[A-Za-z]{1,5}$", user_text):
        code = user_text.upper()
        info = get_stock_info(code, market="US")
        if info is None:
            send_push(user_id, [text_msg(MSG_US_NOT_FOUND.format(code=code))])
            return
        if "error" in info:
            send_push(user_id, [text_msg(MSG_FETCH_ERROR.format(code=code))])
            return
        card = build_stock_card(info)
        send_push(user_id, [FlexMessage(alt_text=info.get("name", code), contents=card)])
        return

    try:
        answer = answer_question(user_text)
        send_push(user_id, [text_msg(answer)])
    except Exception as e:
        logger.error("QA error: %s", e)
        send_push(user_id, [text_msg(MSG_QA_ERROR)])

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")
    try:
        events = parser.parse(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            user_id = event.source.user_id
            user_text = event.message.text
            background_tasks.add_task(process_message, user_id, user_text)

    return PlainTextResponse("OK")  # Returns 200 immediately, background continues

@app.post("/push-report")
async def push_report(request: Request):
        """Nightly analysis report from Cowork, pushed to LINE."""
        data = await request.json()
        push_secret = os.getenv("PUSH_SECRET", "")
        line_user_id = os.getenv("LINE_MY_USER_ID", "")

    if not push_secret or data.get("secret", "") != push_secret:
                raise HTTPException(status_code=401, detail="Unauthorized")
            if not line_user_id:
                        raise HTTPException(status_code=500, detail="LINE_MY_USER_ID not configured")

    message = data.get("message", "")
    if not message:
                raise HTTPException(status_code=400, detail="No message provided")

    chunks = [message[i:i+4900] for i in range(0, len(message), 4900)]
    msgs = [text_msg(chunk) for chunk in chunks[:5]]

    try:
                send_push(line_user_id, msgs)
                logger.info("Push report sent (%d chunk(s))", len(msgs))
                return {"status": "ok", "chunks": len(msgs)}
except Exception as e:
            logger.error("Push report failed: %s", e)
            raise HTTPException(status_code=500, detail=str(e))
    
