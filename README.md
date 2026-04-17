# 《股癌》標的追蹤 MVP

這是一個 0 元成本的自動化 MVP：從 YouTube RSS 找新影片，抓 YouTube 自動字幕，用 Gemini Flash 整理節目提到的公司與股票標的，最後推播到 Telegram。

> 本專案只做資訊整理，不提供投資建議。

## 架構

- Runner：GitHub Actions，每 6 小時檢查一次。
- 來源：YouTube RSS，不需要 YouTube API key。
- 字幕：`youtube-transcript-api` 抓取 YouTube 字幕。
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

## Telegram Bot 設定

1. 在 Telegram 找 `@BotFather` 建立 bot，取得 `TELEGRAM_BOT_TOKEN`。
2. 把 bot 加進你的 channel 或群組。
3. 取得 `TELEGRAM_CHAT_ID`。
   - 私人或群組可先傳訊息給 bot，再用 `https://api.telegram.org/bot<token>/getUpdates` 查 id。
   - Channel 通常會是 `@channel_username` 或 `-100...` 格式。

## 執行方式

Dry run：只抓 RSS 與字幕，不呼叫 Gemini、不發 Telegram、不更新狀態檔。

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

如果要重新處理已在 `processed_videos.json` 的影片：

```bash
uv run podcast-stock --ignore-state
```

## GitHub Actions 設定

在 GitHub repository 的 Settings → Secrets and variables → Actions 新增：

Secrets：

- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `YOUTUBE_CHANNEL_ID`

Variables（可選）：

- `GEMINI_MODEL`，預設為 `gemini-2.5-flash`

Workflow 位於 `.github/workflows/podcast-stock.yml`，會每 6 小時執行，也可以手動 `workflow_dispatch`。

當成功處理新影片後，GitHub Actions 會自動提交更新後的 `processed_videos.json`。

## 輸出格式

Telegram 會收到 Markdown 摘要，包含：

- 本集三大重點。
- 提到的公司與股票代號。
- 主講人態度：偏多、偏空、中立、無明確方向。
- YouTube 自動字幕可能造成的辨識疑點。

如果 Telegram Markdown 格式送出失敗，程式會自動改用純文字重送。

## 風險與限制

- YouTube 自動字幕可能在影片剛發布時尚未產生；程式會跳過該影片，下一次排程再試。
- `youtube-transcript-api` 依賴 YouTube 未公開介面，未來可能因 YouTube 變更而失效。
- Gemini 可能誤判公司名稱或代號；Prompt 已要求不確定時標示「待確認」，但仍建議人工複核。
- MVP 不包含資料庫、儀表板、績效追蹤或投資建議。

## 如何測試

1. 先跑 `uv run podcast-stock --dry-run`，確認 RSS 與字幕抓取正常。
2. 用 `--video-id` 指定一支已知有中文字幕的影片，確認字幕可以抓到。
3. 確認 `.env` 中 Gemini 與 Telegram 設定後，執行 `uv run podcast-stock --video-id VIDEO_ID --title "測試影片"`。
4. 確認 Telegram 收到訊息，且 `processed_videos.json` 新增該影片 ID。
5. 再跑一次同樣指令，不加 `--ignore-state` 時，RSS 模式應不會重複處理已記錄影片。
