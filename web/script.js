let currentConfig = {};
let detectedLive = false;

window.onload = async () => {
    currentConfig = await eel.init_app()();
    updateSettingsUI();
    // 載入預設偏好 (可選)
    loadPreferences(); 
    toggleSubOptions();
};

function updateSettingsUI() {
    document.getElementById('cfg_ffmpeg').value = currentConfig.system_settings.ffmpeg_path || '';
    document.getElementById('cfg_output').value = currentConfig.system_settings.output_directory || '';
}

function loadPreferences() {
    // 將 config 中的預設值填回 UI (簡化版)
    const prefs = currentConfig.default_preferences;
    if(prefs) {
        document.getElementById('vid_ext').value = prefs.video_ext;
        document.getElementById('aud_ext').value = prefs.audio_ext;
        document.getElementById('img_ext').value = prefs.image_ext;
    }
}

function toggleSettings() {
    document.getElementById('settingsPanel').classList.toggle('hidden');
}

function toggleSubOptions() {
    ['sub_video', 'sub_audio', 'sub_cover'].forEach(id => {
        document.getElementById(id).classList.add('hidden');
    });

    const mode = document.querySelector('input[name="downloadMode"]:checked').value;
    if (document.getElementById('sub_' + mode)) {
        document.getElementById('sub_' + mode).classList.remove('hidden');
    }
    
    checkLiveWarning(mode);
}

// 瀏覽檔案/資料夾功能
async function browseFFmpeg() {
    const path = await eel.select_ffmpeg_file()();
    if (path) document.getElementById('cfg_ffmpeg').value = path;
}
async function browseDir() {
    const path = await eel.select_directory()();
    if (path) document.getElementById('cfg_output').value = path;
}
async function saveSettings() {
    currentConfig.system_settings.ffmpeg_path = document.getElementById('cfg_ffmpeg').value;
    currentConfig.system_settings.output_directory = document.getElementById('cfg_output').value;
    
    // 同步保存當前UI選擇作為未來預設
    currentConfig.default_preferences.video_ext = document.getElementById('vid_ext').value;
    currentConfig.default_preferences.audio_ext = document.getElementById('aud_ext').value;
    currentConfig.default_preferences.image_ext = document.getElementById('img_ext').value;

    await eel.update_config(currentConfig)();
    toggleSettings();
    add_log("設定已儲存", "info");
}

// 網址分析
let analyzeTimer;
async function analyzeLink() {
    const url = document.getElementById('urlInput').value.trim();
    const badge = document.getElementById('platformBadge');
    
    clearTimeout(analyzeTimer);
    
    if (!url) {
        badge.classList.add('hidden');
        document.getElementById('liveWarning').classList.add('hidden');
        detectedLive = false;
        return;
    }

    badge.classList.remove('hidden');
    badge.innerText = "分析中...";
    
    analyzeTimer = setTimeout(async () => {
        const info = await eel.analyze_url(url)();
        
        let text = "通用網站";
        if (info.platform === 'youtube') text = "YouTube";
        if (info.platform === 'bilibili') text = "Bilibili";
        if (info.platform === 'twitch') text = "Twitch";
        
        if (info.is_live) text += " (LIVE)";
        
        badge.innerText = text;
        badge.style.color = info.platform === 'generic' ? '#cba6f7' : '#a6e3a1';

        detectedLive = info.is_live;
        checkLiveWarning(document.querySelector('input[name="downloadMode"]:checked').value);
    }, 600);
}

function checkLiveWarning(mode) {
    const warningBox = document.getElementById('liveWarning');
    if (detectedLive && (mode === 'video' || mode === 'audio')) {
        warningBox.classList.remove('hidden');
    } else {
        warningBox.classList.add('hidden');
    }
}

function startDownload() {
    const url = document.getElementById('urlInput').value.trim();
    if (!url) {
        alert("請輸入網址！");
        return;
    }

    const mode = document.querySelector('input[name="downloadMode"]:checked').value;
    
    // 收集詳細選項
    const options = {
        mode: mode,
        is_live_mode: detectedLive,
        // Video Params
        video_quality: document.getElementById('vid_quality').value,
        video_ext: document.getElementById('vid_ext').value,
        // Audio Params
        audio_ext: document.getElementById('aud_ext').value,
        audio_quality: document.getElementById('aud_bitrate').value,
        // Image Params
        image_ext: document.getElementById('img_ext').value,
        // Toggles (預設為 false, 根據模式覆蓋)
        embed_cover: false,
        embed_meta: false
    };

    if (mode === 'video') {
        options.embed_cover = document.getElementById('vid_embed_cover').checked;
        options.embed_meta = document.getElementById('vid_embed_meta').checked;
    } else if (mode === 'audio') {
        options.embed_cover = document.getElementById('aud_embed_cover').checked;
        options.embed_meta = document.getElementById('aud_embed_meta').checked;
    }

    // UI Reset
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('percentNum').innerText = '0%';
    document.getElementById('statusMsg').innerText = '初始化下載引擎...';
    document.getElementById('logConsole').innerHTML = '';

    eel.start_download_task(url, options);
}

// Eel Hooks
eel.expose(update_progress);
function update_progress(percent, msg) {
    document.getElementById('progressBar').style.width = percent + '%';
    document.getElementById('percentNum').innerText = Math.floor(percent) + '%';
    if(msg) document.getElementById('statusMsg').innerText = msg;
}

eel.expose(add_log);
function add_log(msg, level) {
    const consoleDiv = document.getElementById('logConsole');
    const line = document.createElement('div');
    line.innerText = `> ${msg}`;
    if (level === 'error') line.style.color = '#f38ba8';
    if (level === 'warn') line.style.color = '#f9e2af';
    if (level === 'success') line.style.color = '#a6e3a1';
    consoleDiv.appendChild(line);
    consoleDiv.scrollTop = consoleDiv.scrollHeight;
}