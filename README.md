# 《れじぇくろ！》輕量互動劇情引擎 (LegecloPlayer Lite)

> [!IMPORTANT]
> ### ⚖️ 免責聲明與法律條款 (Disclaimer & Legal Notice)
> 
> 1. **僅供技術研究與教育學習 (Academic & Research Purpose Only)**：
>    本專案為開源非商業專案，旨在研究 WebGL 互動式視覺渲染、Spine 2D 骨骼動畫即時重構、音訊串流分塊解碼及數位檔案封存技術。請勿將本專案用於任何形式之商業營利、付費傳播或侵害原著作權人之行為。
> 2. **智慧財產權與著作權歸屬 (Copyright Notice)**：
>    本專案所解析、呈現或關聯之遊戲人物、美術插圖、CG 靜態圖、Spine 骨骼模型、音樂音效、語音台詞與劇本文本，其所有智慧財產權、商標權與著作權均完整歸屬於原遊戲開發商與發行商（**Techcross / Johren / DMM GAMES**）所有。本開源代碼庫**不包含且不託管**任何受版權保護的原廠二進位遊戲素材。
> 3. **非官方與無任何關聯 (No Affiliation & Unofficial)**：
>    本專案為社群技術愛好者之獨立開源專案，與 Techcross、Johren、DMM GAMES 或其關聯企業無任何隸屬、授權、背書或合作關係。使用者因使用本專案而產生之任何爭議或法律責任，均由使用者自行承擔。
> 4. **外部端點與自訂內容責任 (Third-Party CDN & User Responsibilities)**：
>    本引擎支援動態自訂外部資源端點（如自建 Cloudflare R2、私人鏡像伺服器或本地快取路徑）。本專案不提供任何受保護資源之公開下載服務，使用者應自行確保其存取端點與資產之合法授權。
> 5. **權益維護與下架聯繫 (Takedown & Safe Harbor Notice)**：
>    若版權持有人或相關機構認為本代碼庫存在任何疑慮或不妥之處，敬請隨時透過 Issue 或電子郵件聯繫，開發者將在第一時間全力配合說明、修改或移除相關內容。

---

## ✨ 專案特色

1. **模組化按需串流 (On-Demand Caching)**：
   - 支援依章節演出動態讀取語音、背景與動畫差分，無需一次性佔用大量本機儲存空間。
2. **Spine 2D 骨骼渲染優化**：
   - 內建容錯紋理尋址與安全備援機制，大幅提升網頁端 Spine 動態立繪加載穩定性。
3. **端點配置完全解耦**：
   - 支援透過 `config.json` 或環境變數自由指定資源鏡像站（支援官方端點、私人 NAS 或 Cloudflare R2 物件儲存）。
4. **PWA 與跨裝置相容**：
   - 支援 16:9 / 滿版全螢幕、手機直橫向自動適配與離線應用安裝。

---

## 🚀 快速開始

### 方式一：下載開箱即用完整包（推薦一般使用者）
若您不具備 Python 開發環境，請直接前往 **[Releases 頁面](../../releases)** 下載最新發布的綠色壓縮包 `LegecloPlayer_Lite.zip`：
1. 解壓縮至任意目錄（無須安裝）。
2. 雙擊執行 **`啟動播放器.bat`**。
3. 瀏覽器將自動開啟 `http://localhost:8888/` 即可開始體驗。

---

### 方式二：從原始碼運行（開發者 / 多平台）
本專案核心為純 Python + 標準 Web 技術構建，可跨 Windows / macOS / Linux 運行：

1. **複製專案庫**：
   ```bash
   git clone https://github.com/BreezeKitten/LegecloPlayer_Lite.git
   cd LegecloPlayer_Lite
   ```

2. **安裝 Python 相依庫**：
   ```bash
   pip install UnityPy imageio-ffmpeg pillow
   ```
   *(可選)* 音訊解碼若需處理 CRI HCA/ACB 封裝，請確保系統已安裝 `vgmstream` 並加入 PATH。

3. **初始化設定檔**：
   複製設定檔範本為 `config.json`：
   ```bash
   cp config.example.json config.json
   ```
   可依需求自訂連接埠或自建 CDN 端點：
   ```json
   {
     "cdn_base": "https://your-mirror-bucket.com/pcr",
     "port": 8888,
     "auto_open_browser": true
   }
   ```

4. **啟動伺服器**：
   ```bash
   python server.py
   ```
   打開瀏覽器瀏覽 `http://localhost:8888/`。

---

## ⚙️ 進階配置 (config.json)

| 欄位名稱 | 型別 | 預設值 | 說明 |
| :--- | :--- | :--- | :--- |
| `cdn_base` | string | `https://asset-tw.legeclo.johren.games/pcr` | 資源鏡像伺服器基礎 URL（支援 Cloudflare R2 / 自建 CDN） |
| `port` | number | `8888` | 本機 Web 服務監聽埠號（若衝突會自動順延） |
| `auto_open_browser` | boolean | `true` | 啟動完成後是否自動呼叫預設瀏覽器開啟頁面 |

> **環境變數支援**：亦可透過設定環境變數 `LEGECLO_CDN_BASE` 覆蓋設定檔中的端點網址。

---

## 📁 檔案結構說明

```text
LegecloPlayer_Lite/
├── config.example.json    # 外部配置範本 (CDN 端點 / 埠號設定)
├── server.py              # 核心輕量 HTTP 串流伺服器與解碼調度器
├── 一鍵全量回補.py        # 多線程批次資源回補與離線同步工具
├── cdn_manifest.json      # 演出素材映射清單
├── char_catalog.json      # 角色話數索引目錄
├── char_model_map.json    # Spine 骨骼模型對應表
├── char_names.json        # 角色名稱中繼資料
├── web/                   # HTML5/ES6 播放器前端介面與 Spine Runtime
├── assets/                # 播放器預設介面圖示 (預設頭像與背景圖)
├── sync_cache_to_phone.bat# 一鍵同步快取至 Android 手機工具
└── cache/                 # 本地動態運行快取 (依需求即時生成)
```

---

## 📱 手機版連動 (LegecloPlayer Android)

本專案與原生 Android 離線播放器 **[LegecloPlayer_Android](https://github.com/BreezeKitten/LegecloPlayer_Android)** 完整互通相容！
若需將電腦端下載好的快取傳輸至手機，只需將手機插上傳輸線並雙擊執行本目錄中的 **`sync_cache_to_phone.bat`**，即可一鍵將全角色離線快取同步至手機！

---

## 📄 開源授權 (License)

- 本專案自身的腳本與介面代碼採用 **MIT License** 授權。
- 第三方開放原始碼庫（UnityPy、Spine Runtimes、vgmstream 等）版權各歸其原作者所有。
- 專案相關之遊戲商業內容與原廠多媒體素材不在本開源授權範圍內。
