# 《股癌》標的追蹤 MVP

這是一個 0 元成本的自動化 MVP：從 YouTube RSS 找新影片，抓 YouTube 自動字幕，用 Gemini Flash 整理節目提到的公司與股票標的，最後推播到 Telegram。

> 本專案只做資訊整理，不提供投資建議。

## 架構

- Runner：GitHub Actions，每週四與週日 00:00（Asia/Taipei）檢查一次。
- 來源：YouTube RSS，不需要 YouTube API key。
- 字幕：優先用 `youtube-transcript-api` 抓取 YouTube 字幕；沒有字幕時可用本機 Whisper fallback 轉錄音訊。
- LLM：Gemini API，預設 `gemini-2.5-flash`。
- 推播：Telegram Bot API。
- 去重：`processed_videos.json` 記錄已處理影片。

## 本機設定

```bash
uv sync
cp .env.example .env
```

編輯 `.env`：

```bash
GEMINI_API_KEY=你的 Gemini API key
TELEGRAM_BOT_TOKEN=你的 Telegram Bot token
TELEGRAM_CHAT_ID=你的 Telegram chat 或 channel id
YOUTUBE_CHANNEL_ID=謝孟恭 YouTube channel id
```

股癌 YouTube channel id：

```bash
YOUTUBE_CHANNEL_ID=UC23rnlQU_qE3cec9x709peA
```

若要在 YouTube 沒有字幕時自動用本機 Whisper 轉錄，保留預設設定：

```bash
ENABLE_WHISPER_FALLBACK=true
WHISPER_MODEL=small
WHISPER_LANGUAGE=zh
SAVE_OUTPUTS=true
OUTPUT_DIR=runs
```

Whisper fallback 會下載 YouTube 音訊檔，並用 `faster-whisper` 內部的 PyAV 解碼與轉錄，不需要另外安裝 `ffmpeg`。

程式預設會把每支影片的處理結果留在本地：

```text
runs/
  2026-04-18_VIDEO_ID/
    metadata.json
    transcript.txt
    dry_run_summary.md
    summary.md
```

- `metadata.json`：影片 id、標題、連結、發佈時間、處理時間。
- `transcript.txt`：完整逐字稿，來源可能是 YouTube 字幕或 Whisper fallback。
- `dry_run_summary.md`：`--dry-run` 時保存的 dry-run 輸出。
- `summary.md`：正式執行時 Gemini 產生、準備送 Telegram 的摘要。

如果不想保存本地紀錄，可設定：

```bash
SAVE_OUTPUTS=false
```

## Telegram Bot 設定

1. 在 Telegram 找 `@BotFather` 建立 bot，取得 `TELEGRAM_BOT_TOKEN`。
2. 把 bot 加進你的 channel 或群組。
3. 取得 `TELEGRAM_CHAT_ID`。
   - 私人或群組可先傳訊息給 bot，再用 `https://api.telegram.org/bot<token>/getUpdates` 查 id。
   - Channel 通常會是 `@channel_username` 或 `-100...` 格式。

## 執行方式

Dry run：只抓 RSS 與字幕，不呼叫 Gemini、不發 Telegram、不更新狀態檔。若影片沒有 YouTube 字幕且 `ENABLE_WHISPER_FALLBACK=true`，會下載音訊並用本機 Whisper 轉錄。

```bash
uv run podcast-stock --dry-run
```

手動指定影片 ID 測試：

```bash
uv run podcast-stock --video-id VIDEO_ID --title "測試影片" --dry-run
```

正式執行：

```bash
uv run podcast-stock
```

重送已保存的本地摘要到 Telegram，不重新抓 RSS、轉錄或呼叫 Gemini：

```bash
uv run podcast-stock --send-summary-file runs/2026-04-18_VIDEO_ID/summary.md
```

用已保存的逐字稿重新產生投資摘要，不重新抓 RSS 或跑 Whisper：

```bash
uv run podcast-stock --summarize-transcript-file runs/2026-04-18_VIDEO_ID/transcript.txt
```

重新產生後立刻發送 Telegram：

```bash
uv run podcast-stock --summarize-transcript-file runs/2026-04-18_VIDEO_ID/transcript.txt --send-after-summary
```

如果要重新處理已在 `processed_videos.json` 的影片：

```bash
uv run podcast-stock --ignore-state
```

## GitHub Actions 設定

在 GitHub repository 的 Settings → Secrets and variables → Actions 新增：

Secrets（必填，敏感資訊）：

- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Variables（必填，非敏感設定）：

- `YOUTUBE_CHANNEL_ID`：股癌 YouTube channel id，設定為 `UC23rnlQU_qE3cec9x709peA`

Variables（可選，不設定時使用預設值）：

- `GEMINI_MODEL`，預設為 `gemini-2.5-flash`
- `MAX_VIDEOS_PER_RUN`，預設為 `1`
- `ENABLE_WHISPER_FALLBACK`，預設為 `true`
- `WHISPER_MODEL`，預設為 `small`
- `WHISPER_LANGUAGE`，預設為 `zh`
- `SAVE_OUTPUTS`，預設為 `true`
- `OUTPUT_DIR`，預設為 `runs`

目前 workflow 排程位於 `.github/workflows/podcast-stock.yml`：

```yaml
schedule:
  # GitHub Actions cron uses UTC.
  # Runs at 00:00 Asia/Taipei on Thursday and Sunday.
  - cron: "0 16 * * 3,6"
```

也可以到 GitHub Actions 頁面手動執行 `workflow_dispatch`。

當成功處理新影片後，GitHub Actions 會自動提交更新後的 `processed_videos.json`。

## 輸出格式

Telegram 會收到 Markdown 摘要，包含：

- 投資重點摘要。
- 市場與總經。
- 產業與主題。
- 提到的公司與股票代號。
- 主講人對市場方向、風險、部位或交易心態的語氣。
- YouTube 自動字幕可能造成的辨識疑點。

摘要會排除業配、贊助商、折扣碼、產品促銷、生活閒聊，以及和股票或投資沒有關係的內容。

如果 Telegram Markdown 格式送出失敗，程式會自動改用純文字重送。

## 風險與限制

- YouTube 自動字幕可能在影片剛發布時尚未產生；若啟用 Whisper fallback，程式會嘗試下載音訊並本機轉錄。
- Whisper fallback 第一次執行會下載模型，且長影片轉錄時間會明顯比直接抓 YouTube 字幕久。
- Whisper 轉錄可能誤判公司名、股票代號或中英混雜詞，仍建議人工複核。
- `youtube-transcript-api` 依賴 YouTube 未公開介面，未來可能因 YouTube 變更而失效。
- Gemini 可能誤判公司名稱或代號；Prompt 已要求不確定時標示「待確認」，但仍建議人工複核。
- MVP 不包含資料庫、儀表板、績效追蹤或投資建議。

## 如何測試

1. 先跑 `uv run podcast-stock --dry-run`，確認 RSS 與字幕抓取正常。
2. 用 `--video-id` 指定一支已知有中文字幕的影片，確認 YouTube 字幕可以抓到。
3. 用 `--video-id` 指定一支沒有 YouTube 字幕的影片，確認 Whisper fallback 會下載音訊並轉錄。
4. 確認 `.env` 中 Gemini 與 Telegram 設定後，執行 `uv run podcast-stock --video-id VIDEO_ID --title "測試影片"`。
5. 確認 Telegram 收到訊息，且 `processed_videos.json` 新增該影片 ID。
6. 再跑一次同樣指令，不加 `--ignore-state` 時，RSS 模式應不會重複處理已記錄影片。
