# 🚀 Advanced Telegram Channel Media Uploader Bot

Ek ultra-advanced, production-ready Telegram Media Bot jo aapke Telegram Channels par **Previewable Media Files** aur **Smart Sorted Batch Uploads** post karta hai. Chahe photo ho, video ho, PDF ho, audio ho ya kisi dusre channel se **Forwarded Media** ho — ye bot hamesha ensure karta hai ki file apne native preview player / single unified document post format me post ho.

---

## ✨ Key Features (Bot ki Khasiyat)

### 1. 📦 Smart Batch Upload & Custom Sorting Mode (`/batch`)
- **Unlimited Batch Collection**:
  - `/batch` start karne ke baad aap jitna chahein utna media (PDFs, Videos, Photos, Audios, Documents) bot ko send ya forward kar sakte hain.
  - Bot un sabhi files ka metadata (Name, Size, Time, Type, Caption) collect karta rahega aur target channel me turant upload nahi karega.
- **Natural Alphanumeric & Custom Sorting Options**:
  - Collection complete hone ke baad `/endbatch` bhejein. Bot aapse interactive sorting order puchega:
    - 🔤 **Name (A ➔ Z / Z ➔ A)**: Natural smart sorting (e.g. *Chapter 2* hamesha *Chapter 10* se pehle aayega).
    - ⏱️ **Time (Oldest First 1➔N / Newest First N➔1)**: Arrival order ke hisab se sort karein.
    - 📦 **Size (Small ➔ Large / Large ➔ Small)**: File size ke hisab se sequence banayein.
    - 📑 **Type (PDF ➔ Video ➔ Photo / Reverse)**: Media format wise grouped sequence.
    - ⚡ **Original Order**: Jis sequence me aapne bheja tha usi order me send karein.
- **Real-time Batch Inspection**:
  - `/batchstatus` se current batch me collected files ki list aur total count dekh sakte hain.
  - `/cancelbatch` se active batch ko discard kar sakte hain.

---

### 2. 📑 Single Unified Document Post with Embedded 1st-Page Thumbnail
- **Pure First-Page Screenshot Rendering (`thumbnail_engine/`)**:
  - Har PDF, EPUB, XPS, CBZ, Office document ke **Page 1 ka pure high-resolution screenshot** extract hota hai.
  - Page 1 image ko Telegram standard thumbnail format ($\le 320\text{px}$) me convert karke document file ke sath **EXACTLY 1 SINGLE POST** me send kiya jata hai.
- **No Split Posts**:
  - Channel timeline me alag se photo post nahi aati; document file, embedded preview thumbnail, caption, aur inline buttons ek hi unified post me aate hain.
- **Immediate Disk Cleanup**:
  - Downloaded temporary files aur generated thumbnails post hote hi disk se delete (`cleanup_temp_files`) ho jate hain.

---

### 3. 🔄 Memory-Safe Sequential FIFO Upload Queue
- **Async Queue System (`asyncio.Queue`)**:
  - Chahe direct upload ho ya batch upload, files dedicated worker ke through **1-by-1 sequentially post** hoti hain.
- **Zero RAM Spikes / No PC Crash**:
  - Ek samay me sirf 1 file memory me process hoti hai aur turant release ho jati hai.
- **FloodWait Protection**:
  - Telegram rate limits hit hone par worker automatically wait karke bina kisi file ko lose kiye upload resume karta hai.

---

### 4. 🔀 Universal Forwarded Media Support
- Kisi bhi dusre channel, group ya user se koi bhi media forward karein (Photos, Videos, PDFs, Audios, Voice notes).
- Bot media extract karke aapke selected channel me custom watermark aur theme ke sath publish karta hai.

---

### 5. 📢 Central Channel Routing & Promotional Bot Button
- **Central Main Channel Link (`MAIN_CHANNEL_USERNAME`)**:
  - Multi-bot network me har post ke niche ek central main channel ka follow/join button lagaya ja sakta hai.
  - Agar `.env` me configure nahi hai, to dynamic selected channel ka invite link/username automatically use hota hai.
- **Promotional Bot Button (`PROMO_BOT_USERNAME`)**:
  - Har channel post ke niche uploader bot ka promotional inline button automatically attach hota hai (`🤖 Bot: @YourBotUsername`).

---

### 6. 🎬 Intelligent Native Media Formats
- 🖼️ **Photos / Images**: Full visual preview picture format me post hoti hain.
- 🎥 **Playable Videos**: Native Telegram Video player me `supports_streaming=True`, duration aur thumbnail ke sath post hoti hain.
- 🎵 **Native Music & Audio**: Telegram Audio player me track title aur performer ke sath post hoti hain.
- 🎙️ **Voice & Video Notes**: Direct circle video / voice message format me post hoti hain.

---

### 7. 🔒 Master Password Authentication & Multi-Channel Switcher
- Master Password gate with brute-force protection (5 attempts cooldown).
- Automatic target channel discovery jab bot ko channel me Admin banaya jaye.
- `/channels` command se 1-click interactive channel switcher.

---

## 📁 Project Structure

```
telegram-channel-uploader-bot/
├── config/
│   ├── __init__.py
│   └── settings.py          # Configuration & environment loader (.env)
├── database/
│   ├── __init__.py
│   ├── db.py                # Async SQLite database (aiosqlite)
│   └── models.py            # User, Channel, Settings data models
├── handlers/
│   ├── __init__.py
│   ├── admin_events.py      # my_chat_member listener (auto channel detector)
│   ├── auth.py              # Password gate & session management
│   ├── channel_select.py    # Channel switcher inline keyboard & adder
│   ├── media_uploader.py    # FIFO Queue & Worker Engine with Preview Handling
│   ├── settings_menu.py     # Interactive preferences dashboard (/settings)
│   ├── smart_batch.py       # Smart Batch Upload, Natural Sorting & Dispatch
│   └── start.py             # /start dashboard, stats, help guide
├── thumbnail_engine/
│   ├── __init__.py
│   └── generator.py         # Document 1st-Page Screenshot Engine & Temp Cleanup
├── utils/
│   ├── __init__.py
│   ├── media_helper.py      # Media format classification & caption builder
│   └── telegram_checker.py  # Bot admin rights verification
├── .env                     # Credentials & Settings
├── .env.example             # Template configuration
├── requirements.txt         # Dependencies
├── README.md                # Detailed Documentation
└── bot.py                   # Main entry point & Queue Worker manager
```

---

## ⚙️ Installation & Setup (Kaise Chalayein)

### Step 1: Dependencies Install Karein
```powershell
pip install -r requirements.txt
```

### Step 2: `.env` File Configure Karein
Folder me `.env` file open karein aur values set karein:

```env
# 1. Telegram Bot Token from @BotFather
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# 2. Master Password for User Access
MASTER_PASSWORD=admin123

# 3. Queue & Worker Settings
WORKER_COUNT=1
MAX_BOT_DOWNLOAD_MB=20

# 4. Central Channel & Promo Bot Settings (Optional)
MAIN_CHANNEL_USERNAME=shahid24x7free
PROMO_BOT_USERNAME=YourUploaderBot
```

### Step 3: Bot Run Karein (Locally)
```powershell
python bot.py
```

---

## 🌐 Deploy to Render.com (24/7 Free Cloud Hosting)

Bot me **Built-in Lightweight Health-Check Web Server** (`utils/web_server.py`) integrated hai, jisse aap Render ke **Free Web Service** par ise bina kisi port error ke 24/7 host kar sakte hain.

### 📋 Step-by-Step Render Deployment:

1. **GitHub Repository Connect Karein:**
   - Apna code GitHub par push karein.
   - [Render.com Dashboard](https://dashboard.render.com/) open karein aur **New +** ➔ **Web Service** par click karein.
   - Apna GitHub repository select karein.

2. **Service Settings Configure Karein:**
   - **Name:** `telegram-uploader-bot` (ya aapka koi bhi manpasand naam)
   - **Language / Runtime:** `Python 3`
   - **Region:** Any (e.g. *Singapore* ya *Oregon*)
   - **Branch:** `main` (ya `master`)
   - **Build Command:**
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command:**
     ```bash
     python bot.py
     ```
   - **Plan:** `Free`

3. **Environment Variables Add Karein:**
   Render me **"Environment Variables"** tab me jakar niche diye gaye variables add karein:
   - `BOT_TOKEN` : Aapka Telegram Bot Token (from @BotFather)
   - `MASTER_PASSWORD` : Bot unlock karne ka password (e.g. `admin123`)
   - `OWNER_ID` : Aapka Telegram User ID (Optional)
   - `DEFAULT_PREVIEW_MODE` : `True`
   - `WORKER_COUNT` : `1`
   - `MAX_BOT_DOWNLOAD_MB` : `20`
   - `ENABLE_WEB_SERVER` : `True`
   - `MAIN_CHANNEL_USERNAME` : *(Optional)* Central join channel
   - `PROMO_BOT_USERNAME` : *(Optional)* Promo bot username

4. **Deploy & Health Check Verification:**
   - **"Create Web Service"** par click karein.
   - Render automatically `pip install` run karega aur `python bot.py` execute karega.
   - Deploy complete hone par Render aapko ek live URL dega (e.g., `https://your-bot-name.onrender.com`).
   - Browser me `https://your-bot-name.onrender.com/health` open karke check karein, wahan `OK` return hoga.

5. **24/7 Always Active / Keep Alive Setup (Free Tier):**
   - Render ka Free Tier 15 minutes inactive rehne par sleep mode me chala jata hai.
   - Ise 24/7 active rakhne ke liye [Cron-Job.org](https://cron-job.org/) ya [UptimeRobot.com](https://uptimerobot.com/) par free account banayein.
   - Ek naya HTTP Monitor banayein aur apna Render URL set karein:
     - **URL:** `https://your-bot-name.onrender.com/health`
     - **Interval:** Every `5 minutes` or `10 minutes`
   - Isse aapka bot Render par bina ruke hamesha online rahega!

---

## 📖 How to Use (Bot ko Use Kaise Karein)

### 🔹 Method A: Direct Upload (1-by-1 ya Normal Bulk)
1. Bot ko `/start` bhej kar Master Password enter karein.
2. `/channels` se target channel select karein.
3. Koi bhi Photo, Video, PDF ya Audio bhejein ya dusre chat se forward karein.
4. Bot queue ke through sequentially process karke channel me post kar dega.

### 🔹 Method B: Smart Batch Upload & Custom Sorting
1. Bot ko `/batch` bhejein.
2. Ab jitna chahein utna media bhejein (PDFs, Videos, Books, Audios).
3. Sari files bhej lene ke baad `/endbatch` bhejein.
4. Screen par aaye Sorting Menu se apna manpasand order select karein (e.g. **Name A-Z**, **Size**, **Time**, **Type**).
5. Bot sabhi files ko sort karke exact line-by-line sequence me channel me upload kar dega!

---

## 🎮 Bot Commands List

| Command | Description |
| :--- | :--- |
| `/start` | Open Main Dashboard & Login Gate |
| `/channels` | Select or Switch Active Target Channel |
| `/addchannel <@username>` | Manually add a channel where bot is admin |
| `/batch` | 📦 Start a Smart Batch Collection session |
| `/endbatch` | 🏁 Finish batch collection & choose Sorting Order |
| `/batchstatus` | 📋 View list of files in current active batch |
| `/cancelbatch` | 🗑️ Discard active batch without uploading |
| `/settings` | Upload Preferences (Silent mode, Watermark, Auto-Pin, Review mode) |
| `/stats` | View Upload Statistics and Channel Counts |
| `/help` | Detailed Help & Setup Guide |
| `/logout` | Log out and lock the bot session |
