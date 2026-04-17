from __future__ import annotations

from google import genai
from google.genai import types

from .models import Video


def summarize_episode(
    *,
    api_key: str,
    model: str,
    video: Video,
    transcript_text: str,
) -> str:
    if not api_key:
        raise ValueError("GEMINI_API_KEY is required unless --dry-run is used.")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=_build_prompt(video, transcript_text),
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=4096,
        ),
    )

    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response.")

    return text


def build_dry_run_summary(video: Video, transcript_text: str) -> str:
    sample = transcript_text[:1000]
    return "\n".join(
        [
            f"# {video.title}",
            "",
            f"影片：{video.url}",
            "",
            "## Dry Run",
            "已成功抓取逐字稿，但未呼叫 Gemini，也未發送 Telegram。",
            "",
            "## 逐字稿前 1000 字",
            sample,
        ]
    )


def _build_prompt(video: Video, transcript_text: str) -> str:
    return f"""你是一位謹慎的台股與美股研究助理，正在整理《股癌》Podcast 的 YouTube 逐字稿。

請根據逐字稿整理成 Telegram 適合閱讀的繁體中文 Markdown。這不是投資建議，不要加入逐字稿沒有支持的推論。

影片資訊：
- 標題：{video.title}
- 連結：{video.url}
- 發佈時間：{video.published or "未知"}

輸出格式：
# {video.title}

影片：{video.url}

## 本集三大重點
1. ...
2. ...
3. ...

## 提到的公司與標的
| 公司/標的 | 股票代號 | 市場 | 態度 | 重點摘要 |
| --- | --- | --- | --- | --- |
| ... | ... | 台股/美股/其他/待確認 | 偏多/偏空/中立/無明確方向 | ... |

## 逐字稿辨識注意事項
- 列出可能因 YouTube 自動字幕造成的專有名詞、股票代號或人名辨識疑點。

規則：
- 不要捏造股票代號；如果不確定，股票代號填「待確認」。
- 態度只能使用「偏多」、「偏空」、「中立」、「無明確方向」。
- 公司與標的只列逐字稿中實際提到或高度明確可辨識者。
- 摘要要精簡、可行動，但避免任何買賣建議。
- 保留繁體中文。

逐字稿：
{transcript_text}
"""
