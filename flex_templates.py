"""
LINE Flex Message 股票卡片模板

build_stock_card(data) 回傳 dict（FlexBubble 格式）
可直接傳入 FlexMessage(contents=...) 使用

卡片設計：
  ┌───────────────────────────────┐
  │  台積電 (2330)  🏷 上市        │
  │  $945.00                       │
  │  ▲ +15.00  (+1.61%)            │
  ├────────────────────────────────┤
  │  開盤 932  最高 950  最低 930   │
  │  昨收 930  成交 45,231 張       │
  │  PE 20.3x  殖利率 2.1%         │
  ├────────────────────────────────┤
  │  [AI分析]  [52W高低]  [新聞]   │
  └────────────────────────────────┘
"""

import logging

logger = logging.getLogger(__name__)


def build_stock_card(data: dict) -> dict:
    """
    根據股票資料建立 Flex Message Bubble（dict 格式）

    Args:
        data: stock_service 回傳的統一格式 dict

    Returns:
        Flex Message container dict
    """
    name = data.get("name", "")
    code = data.get("code", "")
    market = data.get("market", "TW")
    exchange = data.get("exchange", "")
    price = data.get("price", 0)
    change = data.get("change", 0)
    change_pct = data.get("change_pct", 0)
    currency = data.get("currency", "TWD")
    updated_at = data.get("updated_at", "")

    # 漲跌顏色與符號
    is_up = change >= 0
    change_color = "#FF3B30" if is_up else "#34C759"   # 台灣習慣：漲紅跌綠
    change_arrow = "▲" if is_up else "▼"
    change_text = f"{change_arrow} {abs(change):,.2f}  ({change_pct:+.2f}%)"

    # 貨幣前綴
    currency_prefix = "NT$" if currency == "TWD" else "$"

    # 市場標籤顏色
    market_tag_color = "#06C755" if market == "TW" else "#1DA1F2"
    market_label = f"🇹🇼 {exchange}" if market == "TW" else f"🇺🇸 NYSE/NASDAQ"

    # 次要資訊列（開高低收、成交量）
    secondary_rows = _build_secondary_rows(data, currency_prefix)

    # 基本面資訊列
    fundamental_rows = _build_fundamental_rows(data)

    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"{name}",
                            "weight": "bold",
                            "size": "lg",
                            "color": "#1a1a1a",
                            "flex": 1,
                        },
                        {
                            "type": "text",
                            "text": code,
                            "size": "sm",
                            "color": "#888888",
                        },
                    ],
                    "flex": 1,
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": market_label,
                            "size": "xs",
                            "color": "#ffffff",
                            "align": "center",
                        }
                    ],
                    "backgroundColor": market_tag_color,
                    "paddingAll": "6px",
                    "cornerRadius": "12px",
                    "width": "90px",
                    "height": "28px",
                    "justifyContent": "center",
                },
            ],
            "backgroundColor": "#f8f9fa",
            "paddingAll": "16px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                # 主要價格區
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"{currency_prefix}{price:,.2f}",
                            "size": "3xl",
                            "weight": "bold",
                            "color": change_color,
                        },
                        {
                            "type": "text",
                            "text": change_text,
                            "size": "md",
                            "color": change_color,
                            "margin": "sm",
                        },
                    ],
                    "paddingBottom": "12px",
                },
                # 分隔線
                _divider(),
                # 開高低收成交量
                *secondary_rows,
                # 基本面資訊（若有）
                *([ _divider() ] + fundamental_rows if fundamental_rows else []),
            ],
            "paddingAll": "16px",
            "spacing": "sm",
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                _footer_button(
                    label="🤖 AI分析",
                    text=f"{code} 分析",
                ),
                _footer_button(
                    label="📊 相關新聞",
                    text=f"{name} 最新新聞",
                ),
            ],
            "spacing": "sm",
            "paddingAll": "12px",
        },
    }

    # 加上更新時間
    if updated_at:
        bubble["body"]["contents"].append(
            {
                "type": "text",
                "text": f"更新：{updated_at}",
                "size": "xxs",
                "color": "#aaaaaa",
                "align": "end",
                "margin": "md",
            }
        )

    return bubble


# ── 內部輔助函式 ────────────────────────────────────────────────────────────────

def _build_secondary_rows(data: dict, currency_prefix: str) -> list:
    """建立開高低收成交量的資訊列"""
    rows = []

    # 第一列：開盤 / 最高 / 最低
    row1_items = []
    for label, key in [("開盤", "open"), ("最高", "high"), ("最低", "low")]:
        val = data.get(key)
        if val:
            row1_items.append(_stat_item(label, f"{currency_prefix}{val:,.2f}"))

    if row1_items:
        rows.append(_horizontal_row(row1_items))

    # 第二列：昨收 / 成交量
    row2_items = []
    prev_close = data.get("prev_close")
    if prev_close:
        row2_items.append(_stat_item("昨收", f"{currency_prefix}{prev_close:,.2f}"))

    volume = data.get("volume")
    vol_unit = data.get("volume_unit", "")
    if volume:
        if volume >= 10000:
            vol_str = f"{volume/10000:.1f}萬{vol_unit}"
        else:
            vol_str = f"{volume:,}{vol_unit}"
        row2_items.append(_stat_item("成交量", vol_str))

    if row2_items:
        rows.append(_horizontal_row(row2_items))

    return rows


def _build_fundamental_rows(data: dict) -> list:
    """建立基本面資訊列（PE、殖利率、52週高低、市值等）"""
    rows = []
    items = []

    pe = data.get("pe_ratio")
    if pe:
        items.append(_stat_item("本益比", f"{pe}x"))

    dy = data.get("dividend_yield")
    if dy:
        items.append(_stat_item("殖利率", f"{dy}%"))

    market_cap = data.get("market_cap")
    if market_cap:
        items.append(_stat_item("市值", str(market_cap)))

    # 每行最多3個，超過就換行
    for i in range(0, len(items), 3):
        chunk = items[i:i+3]
        rows.append(_horizontal_row(chunk))

    # 52週區間（單獨一列）
    w52h = data.get("52w_high")
    w52l = data.get("52w_low")
    if w52h and w52l:
        currency_prefix = "NT$" if data.get("currency") == "TWD" else "$"
        rows.append(
            _horizontal_row([
                _stat_item("52W高", f"{currency_prefix}{w52h:,.2f}"),
                _stat_item("52W低", f"{currency_prefix}{w52l:,.2f}"),
            ])
        )

    return rows


def _stat_item(label: str, value: str) -> dict:
    """單個統計項目（標籤 + 數值）"""
    return {
        "type": "box",
        "layout": "vertical",
        "contents": [
            {
                "type": "text",
                "text": label,
                "size": "xxs",
                "color": "#888888",
            },
            {
                "type": "text",
                "text": value,
                "size": "sm",
                "weight": "bold",
                "color": "#333333",
            },
        ],
        "flex": 1,
    }


def _horizontal_row(items: list) -> dict:
    """水平排列的資訊列"""
    return {
        "type": "box",
        "layout": "horizontal",
        "contents": items,
        "margin": "sm",
    }


def _divider() -> dict:
    return {
        "type": "separator",
        "margin": "md",
        "color": "#e0e0e0",
    }


def _footer_button(label: str, text: str) -> dict:
    """底部快速回覆按鈕（點擊後傳送文字給 bot）"""
    return {
        "type": "button",
        "action": {
            "type": "message",
            "label": label,
            "text": text,
        },
        "style": "secondary",
        "height": "sm",
        "flex": 1,
        "color": "#f0f0f0",
    }
