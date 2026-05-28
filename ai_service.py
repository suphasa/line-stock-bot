"""
AI Service using Claude API.
Pure ASCII source - Chinese text uses Unicode escapes.
"""
import anthropic
import os
import logging


logger = logging.getLogger(__name__)


MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 512


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
