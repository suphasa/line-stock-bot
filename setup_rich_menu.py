"""
Rich Menu 設定腳本（一次性執行）

執行方式：
    python setup_rich_menu.py

這會在你的 LINE Official Account 建立底部選單：
  ┌──────────┬──────────┬──────────┐
  │  📈查股價 │ 🤖AI分析 │ 📰市場新聞│
  ├──────────┼──────────┼──────────┤
  │ 💼我的持股│ 🔔價格提醒│ ❓使用說明│
  └──────────┴──────────┴──────────┘
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

LINE_API_BASE = "https://api.line.me/v2/bot"


def create_rich_menu() -> str:
    """建立 Rich Menu，回傳 richMenuId"""

    rich_menu_body = {
        "size": {"width": 2500, "height": 843},
        "selected": True,
        "name": "股票AI選單",
        "chatBarText": "📈 股票選單",
        "areas": [
            # 上排左：查股價
            {
                "bounds": {"x": 0, "y": 0, "width": 833, "height": 421},
                "action": {
                    "type": "message",
                    "text": "📈 查股價\n請輸入股票代碼，例如：2330（台股）或 AAPL（美股）",
                },
            },
            # 上排中：AI分析
            {
                "bounds": {"x": 833, "y": 0, "width": 834, "height": 421},
                "action": {
                    "type": "message",
                    "text": "🤖 AI分析模式\n請直接輸入你的股票問題，例如：「台積電現在值得買嗎？」",
                },
            },
            # 上排右：市場新聞
            {
                "bounds": {"x": 1667, "y": 0, "width": 833, "height": 421},
                "action": {
                    "type": "message",
                    "text": "📰 今日台股市場新聞",
                },
            },
            # 下排左：我的持股
            {
                "bounds": {"x": 0, "y": 421, "width": 833, "height": 422},
                "action": {
                    "type": "message",
                    "text": "💼 我的持股",
                },
            },
            # 下排中：價格提醒
            {
                "bounds": {"x": 833, "y": 421, "width": 834, "height": 422},
                "action": {
                    "type": "message",
                    "text": "🔔 價格提醒\n請輸入格式：提醒 2330 > 1000（當股價超過1000時通知我）",
                },
            },
            # 下排右：使用說明
            {
                "bounds": {"x": 1667, "y": 421, "width": 833, "height": 422},
                "action": {
                    "type": "message",
                    "text": "❓ 使用說明",
                },
            },
        ],
    }

    resp = requests.post(
        f"{LINE_API_BASE}/richmenu",
        headers=HEADERS,
        data=json.dumps(rich_menu_body),
    )

    if resp.status_code != 200:
        print(f"❌ 建立 Rich Menu 失敗：{resp.status_code}")
        print(resp.text)
        return ""

    rich_menu_id = resp.json()["richMenuId"]
    print(f"✅ Rich Menu 建立成功：{rich_menu_id}")
    return rich_menu_id


def upload_rich_menu_image(rich_menu_id: str):
    """
    上傳 Rich Menu 背景圖片
    圖片規格：2500 x 843 px，JPEG/PNG，< 1MB
    請先準備好圖片放在 assets/rich_menu.png
    """
    image_path = "assets/rich_menu.png"
    if not os.path.exists(image_path):
        print(f"⚠️  找不到圖片 {image_path}，跳過圖片上傳（選單仍可使用）")
        print("   你可以之後在 LINE Official Account Manager 手動設定圖片")
        return

    with open(image_path, "rb") as f:
        resp = requests.post(
            f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
            headers={
                "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
                "Content-Type": "image/png",
            },
            data=f.read(),
        )

    if resp.status_code == 200:
        print("✅ Rich Menu 圖片上傳成功")
    else:
        print(f"⚠️  圖片上傳失敗：{resp.status_code} - {resp.text}")


def set_default_rich_menu(rich_menu_id: str):
    """設定為預設 Rich Menu（所有用戶都會看到）"""
    resp = requests.post(
        f"{LINE_API_BASE}/user/all/richmenu/{rich_menu_id}",
        headers=HEADERS,
    )
    if resp.status_code == 200:
        print("✅ 已設為預設 Rich Menu")
    else:
        print(f"❌ 設定預設失敗：{resp.status_code} - {resp.text}")


def list_rich_menus():
    """列出目前所有 Rich Menu（除錯用）"""
    resp = requests.get(f"{LINE_API_BASE}/richmenu/list", headers=HEADERS)
    menus = resp.json().get("richmenus", [])
    print(f"\n目前兕有 {len(menus)} 個 Rich Menu：")
    for m in menus:
        print(f"  - {m['richMenuId']} | {m['name']}")
    return menus


def delete_all_rich_menus():
    """刪除所有 Rich Menu（重置用）"""
    menus = list_rich_menus()
    for m in menus:
        mid = m["richMenuId"]
        resp = requests.delete(f"{LINE_API_BASE}/richmenu/{mid}", headers=HEADERS)
        status = "✅" if resp.status_code == 200 else "❌"
        print(f"  {status} 刪除 {mid}")


if __name__ == "__main__":
    print("=" * 50)
    print("  LINE 股票 Bot — Rich Menu 設定")
    print("=" * 50)

    print("\n[1/3] 建立 Rich Menu...")
    rich_menu_id = create_rich_menu()

    if rich_menu_id:
        print("\n[2/3] 上傳背景圖片...")
        upload_rich_menu_image(rich_menu_id)

        print("\n[3/3] 設定為預設選單...")
        set_default_rich_menu(rich_menu_id)

        print("\n🎉 完成！重新開啟 LINE 聊天室即可看到選單")
    else:
        print("\n❌ 設定失敗，請檢查 LINE_CHANNEL_ACCESS_TOKEN 是否正確")
