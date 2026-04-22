from __future__ import annotations

import logging
import time

from google import genai
from google.genai import errors
from google.genai import types

from .models import Video

logger = logging.getLogger(__name__)

RETRYABLE_GEMINI_STATUS_CODES = {429, 500, 502, 503, 504}
GEMINI_MAX_ATTEMPTS = 4
GEMINI_RETRY_DELAYS_SECONDS = (30, 90, 180)


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
    response = _generate_content_with_retry(
        client=client,
        model=model,
        prompt=_build_prompt(video, transcript_text),
    )

    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response.")

    finish_reason = _finish_reason(response)
    if finish_reason and finish_reason != "STOP":
        raise RuntimeError(f"Gemini response did not finish cleanly: {finish_reason}")

    return text


def _generate_content_with_retry(
    *,
    client: genai.Client,
    model: str,
    prompt: str,
) -> object:
    last_error: errors.APIError | None = None

    for attempt in range(1, GEMINI_MAX_ATTEMPTS + 1):
        try:
            return client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=32768,
                ),
            )
        except errors.APIError as exc:
            last_error = exc
            status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if (
                status_code not in RETRYABLE_GEMINI_STATUS_CODES
                or attempt >= GEMINI_MAX_ATTEMPTS
            ):
                raise

            delay = GEMINI_RETRY_DELAYS_SECONDS[attempt - 1]
            logger.warning(
                "Gemini request failed with retryable status %s; retrying in %s seconds "
                "(attempt %s/%s).",
                status_code,
                delay,
                attempt + 1,
                GEMINI_MAX_ATTEMPTS,
            )
            time.sleep(delay)

    if last_error:
        raise last_error
    raise RuntimeError("Gemini request failed before receiving a response.")


def _finish_reason(response: object) -> str:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return ""

    finish_reason = getattr(candidates[0], "finish_reason", "")
    return getattr(finish_reason, "name", str(finish_reason))


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

你的任務不是完整節目摘要，而是萃取「投資情報」。只保留與股票、投資、市場、產業、總經、公司基本面、ETF、債券、匯率、商品、資產配置、交易心理、AI/半導體/科技趨勢有關的內容。

必須排除：
- 業配、贊助商、折扣碼、產品促銷、導購連結。
- 日常生活閒聊、節目效果、笑話、親子、旅遊、飲食、保養、醫美、遊戲等無投資關聯內容。
- 只有比喻但沒有實質投資觀點的內容。
- 無法從逐字稿確認的公司、股票代號或市場推論。

如果一段內容同時包含業配與投資比喻，只保留可獨立成立的投資觀點，移除品牌、商品、折扣與購買資訊。

影片資訊：
- 標題：{video.title}
- 連結：{video.url}
- 發佈時間：{video.published or "未知"}

輸出格式：
# {video.title}

影片：{video.url}

## 投資重點摘要
- 列出本集所有有資訊量的投資觀點，不要硬壓成三點。
- 每點要說明主持人的觀點、理由、限制或不確定性。

## 市場與總經
- 只列與大盤、利率、通膨、匯率、資金流、景氣循環、政策、風險偏好有關的內容。
- 若逐字稿沒有相關內容，寫「無明確提及」。

## 產業與主題
- 整理 AI、半導體、科技、金融、能源、消費、ETF 或其他投資主題。
- 若逐字稿沒有相關內容，寫「無明確提及」。

## 提到的公司與標的
| 公司/標的 | 股票代號 | 市場 | 態度 | 重點摘要 | 信心 |
| --- | --- | --- | --- | --- | --- |
| ... | ... | 台股/美股/其他/待確認 | 偏多/偏空/中立/無明確方向 | ... | 高/中/低 |

## 主持人觀點與語氣
- 整理主持人對市場方向、風險、部位或交易心態的語氣。
- 不要寫成投資建議。

## 逐字稿辨識注意事項
- 列出可能因自動轉錄造成的專有名詞、股票代號或人名辨識疑點。

規則：
- 不要捏造股票代號；如果不確定，股票代號填「待確認」。
- 態度只能使用「偏多」、「偏空」、「中立」、「無明確方向」。
- 公司與標的只列逐字稿中實際提到或高度明確可辨識者；不要把業配品牌列入標的，除非主持人明確討論其投資價值。
- 摘要要精簡但完整；如果投資相關內容很多，請充分展開，不要過度壓縮。
- 排除所有業配與無投資關聯內容，不要在輸出中提及贊助商、折扣、產品功效或購買連結。
- 保留繁體中文。

逐字稿：
{transcript_text}
"""
