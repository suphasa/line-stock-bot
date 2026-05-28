            f"\u76ee\u524d\u50f9\u683c\uff1a{price} {currency}\n"
            f"\u6f32\u8dcc\uff1a{change:+.2f} ({change_pct:+.2f}%)\n"
            f"52\u9031\u9ad8\uff1a{high_52w}\n"
            f"52\u9031\u4f4e\uff1a{low_52w}\n"
            f"\u6210\u4ea4\u91cf\uff1a{volume:,}\n"
        )
        pe_ratio = stock_data.get("pe_ratio")
        if pe_ratio:
            stock_summary += f"P/E\u6bd4\uff1a{pe_ratio}\n"
        market_cap = stock_data.get("market_cap")
        if market_cap:
            stock_summary += f"\u5e02\u5080\uff1a{market_cap}\n"
        if user_question:
            user_msg = (
                f"\u4ee5\u4e0b\u662f{name}({code})\u7684\u80a1\u7968\u8cc7\u6599\uff1a\n\n"
                f"{stock_summary}\n"
                f"\u7528\u6236\u554f\u984c\uff1a{user_question}"
            )
        else:
            user_msg = (
                f"\u8acb\u5206\u6790\u4ee5\u4e0b{name}({code})\u7684\u80a1\u7968\u8cc7\u6599\uff1a\n\n"
                f"{stock_summary}\n"
                "\u8acb\u63d0\u4f9b\u7d9c\u5408\u5206\u6790\u3002"
            )
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}]
        )
        return message.content[0].text
    except Exception as e:
        logger.error(f"Error: {e}")
        return "\u5c0d\u4e0d\u8d77\uff0cAI\u5206\u6790\u670d\u52d9\u66ab\u6642\u7121\u6cd5\u4f7f\u7528\uff0c\u8acb\u7a0d\u5f8c\u518d\u8a66\u3002"
            f"\u80a1\u7968\u540d\u7a31\uff1a{name}\n"

蜈ｩ遞ｮ菴ｿ逕ｨ諠�｢�ｼ
1. answer_question(question)   窶 邏碑�辟ｶ隱櫁ｨ閧｡逾ｨ蝠冗ｭ
2. analyze_stock_with_ai(data) 窶 邨仙粋蜊ｳ譎りぃ逾ｨ雉�侭蛛壽ｷｱ蠎ｦ蛻�梵
"""

import os
import logging
import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# 笏笏 Claude 螳｢謌ｶ遶ｯ 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏
_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-opus-4-6"
MAX_TOKENS = 1024

# 笏笏 System Prompt 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏
EXPERT_SYSTEM_PROMPT = """菴譏ｯ荳菴榊ｰ域･ｭ逧�ぃ逾ｨ蛻�梵蟶ｫ�悟錐蜿ｫ縲碁仭雋｡縲搾ｼ悟ｰ育ｲｾ蜿ｰ轣｣閧｡蟶り�鄒手ぃ縲

## 菴逧�音鮟
- 莉･郢�ｫ比ｸｭ譁�屓遲費ｼ瑚ｪ樊ｰ｣隕ｪ蛻�ｽ�ｰ域･ｭ
- 蝟�畑謨ｸ謫夊�豈碑ｼ�ｪｪ譏主撫鬘
- 蛻�梵豸ｵ闢区橿陦馴擇縲∝渕譛ｬ髱｢縲∫ｱ檎｢ｼ髱｢
- 蝗樒ｭ皮ｲｾ邁｡譛蛾㍾鮟橸ｼ500蟄嶺ｻ･蜈ｧ�会ｼ御ｸ榊ｻ｢隧ｱ

## 驥崎ｦ∝次蜑
- 邨募ｰ堺ｸ肴署萓帶�遒ｺ逧�瑚ｲｷ/雉｣縲肴欠莉､�瑚梧弍謠蝉ｾ帙悟ｮ｢隗蛻�梵闊�純閠�
- 蝗樒ｭ皮ｵ仙ｰｾ蠢�亥刈荳奇ｼ壹娯國� 莉･荳顔ぜ蛻�梵蜿��ｼ碁撼謚戊ｳ�ｻｺ隴ｰ�梧兜雉�怏鬚ｨ髫ｪ�瑚ｫ玖�陦悟愛譁ｷ縲ゅ
- 荳咲｢ｺ螳夂噪雉�ｨ贋ｸ崎ｦ∫懸貂ｬ�檎峩隱ｪ縲碁怙隕∵衍隧｢譛譁ｰ雉�侭謇崎�遒ｺ隱阪
"""
AI Service using Claude API.
Pure ASCII source - Chinese text uses Unicode escapes.
"""
import anthropic
import os
import logging

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-6"
MAX_TOKENS = 1024

EXPERT_SYSTEM_PROMPT = "\u4f60\u662f\u4e00\u4f4d\u5c08\u696d\u7684\u80a1\u7968\u5206\u6790\u5e2b\uff0c\u64c5\u9577\u53f0\u7063\u80a1\u5e02\u548c\u7f8e\u5e02\u5206\u6790\u3002\n\u8acb\u7528\u7e41\u9ad4\u4e2d\u6587\u56de\u7b54\u3002\n\n\u4f60\u80fd\u5920\uff1a\n1. \u89e3\u91cb\u80a1\u5e02\u884c\u60c5\u548c\u8da8\u52e2\n2. \u5206\u6790\u500b\u80a1\u57fa\u672c\u9762\u548c\u6280\u8853\u9762\n3. \u89e3\u91cb\u80a1\u5e02\u6307\u6a19\u548c\u8853\u8a9e\n4. \u63d0\u4f9b\u6295\u8cc7\u5efa\u8b70\uff08\u4e0d\u69cb\u6210\u6295\u8cc7\u5efa\u8b70\uff09\n5. \u5206\u6790\u7e3d\u9ad4\u7d93\u6fdf\u548c\u7522\u696d\u8da8\u52e2\n\n\u8acb\u4fdd\u6301\u5c08\u696d\u3001\u5ba2\u89c0\uff0c\u4e26\u63d0\u9192\u7528\u6236\u6295\u8cc7\u6709\u98a8\u96aa\u3002"

ANALYSIS_SYSTEM_PROMPT = "\u4f60\u662f\u4e00\u4f4d\u5c08\u696d\u7684\u80a1\u7968\u5206\u6790\u5e2b\u3002\u6839\u64da\u63d0\u4f9b\u7684\u80a1\u7968\u8cc7\u6599\uff0c\u7d66\u51fa\u5c08\u696d\u7684\u5206\u6790\u3002\n\n\u5206\u6790\u5167\u5bb9\u5305\u62ec\uff1a\n1. \u76ee\u524d\u50f9\u683c\u548c\u6f32\u52d5\u5206\u6790\n2. \u8207\u6b77\u53f2\u9ad8\u4f4e\u6bd4\u8f03\n3. \u57fa\u672c\u9762\u8a55\u4f30\uff08\u5982\u6709\u8cc7\u6599\uff09\n4. \u77ed\u671f\u8da8\u52e2\u5224\u65b7\n5. \u98a8\u96aa\u63d0\u9192\n\n\u8acb\u7528\u7e41\u9ad4\u4e2d\u6587\u56de\u7b54\uff0c\u4fdd\u6301\u5c08\u696d\u5ba2\u89c0\u3002"

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
            messages=[{"role": "user", "content": question}]
        )
        return message.content[0].text
    except Exception as e:
        logger.error(f"Error: {e}")
        return "\u5c0d\u4e0d\u8d77\uff0cAI\u670d\u52d9\u66ab\u6642\u7121\u6cd5\u4f7f\u7528\uff0c\u8acb\u7a0d\u5f8c\u518d\u8a66\u3002"


def analyze_stock_with_ai(stock_data: dict, user_question: str = "") -> str:
    try:
        client = _get_client()
        name = stock_data.get("name", "")
        code = stock_data.get("code", "")
        price = stock_data.get("price", 0)
        change = stock_data.get("change", 0)
        change_pct = stock_data.get("change_pct", 0)
        high_52w = stock_data.get("high_52w", "N/A")
        low_52w = stock_data.get("low_52w", "N/A")
        volume = stock_data.get("volume", 0)
        market = stock_data.get("market", "TW")
        currency = "TWD" if market == "TW" else "USD"
        stock_summary = (
            f"\u80a1\u7968\u4ee3\u78bc\uff1a{code}\n"
