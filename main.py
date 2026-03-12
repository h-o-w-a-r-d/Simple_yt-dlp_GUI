import os
import sys
import subprocess
import json
import shutil
import threading
import time

# --- 1. 自動依賴檢查 ---
def install(package):
    print(f"[系統] 正在安裝必要套件: {package}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

REQUIRED_PACKAGES = ['eel', 'yt-dlp', 'requests', 'mutagen']
for package in REQUIRED_PACKAGES:
    try:
        __import__(package.replace('-', '_'))
    except ImportError:
        try:
            install(package)
        except Exception as e:
            print(f"[錯誤] 無法安裝 {package}: {e}")
            sys.exit(1)

import eel
from yt_dlp import YoutubeDL

# --- 2. 設定管理 ---
CONFIG_FILE = 'config.json'
DEFAULT_CONFIG = {
    "system_settings": {
        "ffmpeg_path": "",
        "output_directory": "Downloads",
        "theme": "dark"
    },
    "default_preferences": {
        "video_ext": "mp4",
        "audio_ext": "mp3",
        "image_ext": "jpg",
        "audio_bitrate": "192",
        "embed_thumbnail": True,
        "embed_metadata": True,
        "video_resolution": "best"
    },
    "advanced": {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "retries": 10,
        "fragment_retries": 10,
        "check_dependencies_on_startup": True
    }
}

current_config = {}

def load_or_create_config():
    global current_config
    system_ffmpeg = shutil.which("ffmpeg")
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                current_config = json.load(f)
        except:
            current_config = DEFAULT_CONFIG
    else:
        current_config = DEFAULT_CONFIG
        if system_ffmpeg:
            current_config["system_settings"]["ffmpeg_path"] = system_ffmpeg
        save_config()
    
    if not current_config["system_settings"]["ffmpeg_path"] and system_ffmpeg:
        current_config["system_settings"]["ffmpeg_path"] = system_ffmpeg

def save_config():
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(current_config, f, indent=4, ensure_ascii=False)

def log_to_frontend(msg, level="info"):
    print(f"[{level.upper()}] {msg}")
    eel.add_log(msg, level)

# --- 3. 核心功能 ---

@eel.expose
def init_app():
    load_or_create_config()
    return current_config

@eel.expose
def update_config(new_settings):
    global current_config
    current_config = new_settings
    save_config()

@eel.expose
def select_directory():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    path = filedialog.askdirectory()
    root.destroy()
    return path

@eel.expose
def select_ffmpeg_file():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    path = filedialog.askopenfilename(filetypes=[("Executable", "*.exe"), ("All Files", "*.*")])
    root.destroy()
    return path

@eel.expose
def analyze_url(url):
    """通用分析：現在全部都視為 yt-dlp 支援的網站"""
    result = {"platform": "universal", "is_live": False}
    if not url: return result
    
    # 簡單標記平台名稱供前端顯示 UI 用，實際下載邏輯已統一
    lower_url = url.lower()
    if "youtube" in lower_url or "youtu.be" in lower_url:
        result["platform"] = "youtube"
    elif "bilibili" in lower_url or "bv" in lower_url:
        result["platform"] = "bilibili"
    elif "twitch" in lower_url:
        result["platform"] = "twitch"
    else:
        result["platform"] = "generic" # 其他網站

    # 直播關鍵字偵測
    if "live" in lower_url or "twitch.tv" in lower_url and "/videos/" not in lower_url and "/clip/" not in lower_url:
        result["is_live"] = True
        
    return result

class MyLogger:
    def debug(self, msg): print(msg) # 暫時開啟 debug 看詳細 logs
    def info(self, msg): print(msg)
    def warning(self, msg): log_to_frontend(f"警告: {msg}", "warn")
    def error(self, msg): log_to_frontend(f"錯誤: {msg}", "error")

def progress_hook(d):
    if d['status'] == 'downloading':
        try:
            p = d.get('_percent_str', '0%').replace('%','')
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')
            eel.update_progress(float(p), f"下載中: {speed} | 剩餘: {eta}")
        except: pass
    elif d['status'] == 'finished':
        eel.update_progress(100, "下載完成，正在進行轉檔與嵌入處理...")

@eel.expose
def start_download_task(url, options):
    threading.Thread(target=_download_worker, args=(url, options), daemon=True).start()

def _download_worker(url, options):
    cfg = current_config
    ffmpeg_path = cfg["system_settings"]["ffmpeg_path"]
    
    if not ffmpeg_path or not os.path.exists(ffmpeg_path):
        log_to_frontend("找不到 FFmpeg，請設定路徑！", "error")
        return

    mode = options['mode']
    # 根據模式建立子資料夾
    output_dir = os.path.join(cfg["system_settings"]["output_directory"], mode.capitalize())
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    log_to_frontend(f"啟動萬能引擎: {url}", "info")
    
    # --- 1. 初始化 PostProcessors 列表 ---
    # 這是關鍵，我們要把所有處理動作按順序排隊
    post_processors = []

    # --- 2. yt-dlp 基礎設定 ---
    ydl_opts = {
        'ffmpeg_location': ffmpeg_path,
        'logger': MyLogger(),
        'progress_hooks': [progress_hook],
        'outtmpl': os.path.join(output_dir, '[%(uploader)s] %(title)s [%(id)s].%(ext)s'),
        'retries': cfg['advanced']['retries'],
        'fragment_retries': cfg['advanced']['fragment_retries'],
        'user_agent': cfg['advanced']['user_agent'],
        'noplaylist': True,
        'writethumbnail': False, 
    }

    # --- 3. 處理封面與 Metadata (通用邏輯) ---
    if options.get('embed_cover'):
        ydl_opts['writethumbnail'] = True
        # A. 強制將封面轉為 jpg (MP4 必須是 jpg 才能嵌入)
        post_processors.append({
            'key': 'FFmpegThumbnailsConvertor',
            'format': 'jpg',
        })
        # B. 加入嵌入封面的動作
        post_processors.append({'key': 'EmbedThumbnail'})
    
    if options.get('embed_meta'):
        # 加入嵌入 Metadata 的動作
        post_processors.append({
            'key': 'FFmpegMetadata',
            'add_metadata': True,
        })

    # --- 4. 根據模式配置格式 ---
    try:
        # 1. 影片模式
        if mode == 'video':
            quality_map = {
                'best': "bestvideo+bestaudio/best",
                '4k': "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
                '1080': "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                '720': "bestvideo[height<=720]+bestaudio/best[height<=720]"
            }
            ydl_opts['format'] = quality_map.get(options['video_quality'], 'bestvideo+bestaudio/best')
            ydl_opts['merge_output_format'] = options['video_ext']

        # 2. 音訊模式
        elif mode == 'audio':
            ydl_opts['format'] = 'bestaudio/best'
            # 音訊轉檔處理器必須排在最前面 (index 0)
            post_processors.insert(0, {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': options['audio_ext'],
                'preferredquality': options['audio_quality'],
            })

        # 3. 純封面模式
        elif mode == 'cover':
            ydl_opts['skip_download'] = True
            ydl_opts['writethumbnail'] = True
            post_processors = [{
                'key': 'FFmpegThumbnailsConvertor',
                'format': options['image_ext'], 
                'when': 'before_dl' 
            }]

        # 4. 純 Metadata 模式
        elif mode == 'metadata':
            ydl_opts['skip_download'] = True
            ydl_opts['writeinfojson'] = True

        # --- 5. 整合處理器 ---
        if post_processors:
            # 如果是音訊且格式是 opus，我們過濾掉 FFmpegMetadata 
            # 因為 yt-dlp 的 FFmpegExtractAudio 通常已經處理好基礎標籤了
            if mode == 'audio' and options.get('audio_ext') == 'opus':
                post_processors = [pp for pp in post_processors if pp['key'] != 'FFmpegMetadata']
            
            ydl_opts['postprocessors'] = post_processors

        # 直播模式額外處理
        if options.get('is_live_mode'):
            log_to_frontend("⚠️ 啟動直播錄製 (DVR) 模式", "warn")
            ydl_opts['live_from_start'] = True
            # 如果是直播，強制移除嵌入封面動作（直播流極易損壞）
            if mode == 'video':
                ydl_opts['postprocessors'] = [pp for pp in post_processors if pp['key'] != 'EmbedThumbnail']

        # --- 6. 執行下載 ---
        with YoutubeDL(ydl_opts) as ydl:
            # extract_info 會觸發下載，並回傳影片資訊
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # 取得最終輸出的副檔名路徑
            final_path = os.path.splitext(filename)[0] + "." + options['audio_ext']
            # 取得封面路徑 (yt-dlp 下載的封面通常在 filename 同一個位置，且轉成 .jpg 了)
            thumbnail_path = os.path.splitext(filename)[0] + ".jpg"

        # --- 7. 針對 Opus 的 Mutagen 補救計畫 (標籤 + 封面) ---
        if mode == 'audio' and options.get('audio_ext') == 'opus':
            try:
                from mutagen.oggopus import OggOpus
                from mutagen.flac import Picture
                import base64

                audio = OggOpus(final_path)

                # 寫入文字標籤
                if options.get('embed_meta'):
                    audio["title"] = info.get("title", "")
                    audio["artist"] = info.get("uploader", "")
                    audio["date"] = info.get("upload_date", "")
                    audio["comment"] = f"URL: {url}"

                # 寫入封面圖片
                if options.get('embed_cover') and os.path.exists(thumbnail_path):
                    pic = Picture()
                    with open(thumbnail_path, "rb") as f:
                        pic.data = f.read()
                    pic.type = 3  # Front Cover
                    pic.mime = "image/jpeg"
                    pic.desc = "front cover"
                    
                    # Opus 存放圖片的方式比較特別，需要編碼成 string
                    picture_data = base64.b64encode(pic.write()).decode('ascii')
                    audio["metadata_block_picture"] = [picture_data]

                audio.save()
                log_to_frontend("🎨 已透過 Mutagen 嵌入封面與標籤 (Opus 專用)", "success")

                # 清理暫存的 jpg 封面檔 (選配)
                # if os.path.exists(thumbnail_path): os.remove(thumbnail_path)

            except Exception as e:
                log_to_frontend(f"⚠️ Mutagen 處理失敗: {e}", "warn")
        
        log_to_frontend("✅ 任務執行完畢", "success")
        eel.update_progress(100, "完成")

    except Exception as e:
        log_to_frontend(f"❌ 錯誤: {str(e)}", "error")
        eel.update_progress(0, "失敗")

# --- 4. 啟動 ---
if __name__ == '__main__':
    load_or_create_config()
    eel.init('web')
    try:
        eel.start('index.html', size=(950, 850))
    except (SystemExit, MemoryError, KeyboardInterrupt):
        pass