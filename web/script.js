// 全域變數存設定
let currentConfig = {};
let detectedLive = false;

// 初始化
window.onload = async () => {
    currentConfig = await eel.init_app()();
    updateSettingsUI();
    toggleSubOptions(); // 初始化選項顯示
};

// UI 更新函式
function updateSettingsUI() {
    document.getElementById('cfg_ffmpeg').value = currentConfig.system_settings.ffmpeg_path || '未設定';
    document.getElementById('cfg_output').value = currentConfig.system_settings.output_directory || '未設定';
}

function toggleSettings() {
    document.getElementById('settingsPanel').classList.toggle('hidden');
}

function toggleSubOptions() {
    // 隱藏所有子選項
    document.getElementById('sub_video').classList.add('hidden');
    document.getElementById('sub_audio').classList.add('hidden');

    // 根據選擇顯示
    const mode = document.querySelector('input[name="downloadMode"]:checked').value;
    if (mode === 'video') document.getElementById('sub_video').classList.remove('hidden');
    if (mode === 'audio') document.getElementById('sub_audio').classList.remove('hidden');
    
    // 檢查直播警告是否需要強制顯示 (如果網址偵測為 live 且模式為 video/audio)
    checkLiveWarning(mode);
}

// 瀏覽按鈕
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
    await eel.update_config(currentConfig)();
    toggleSettings();
    addLog("設定已儲存。", "info");
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
    badge.innerText = "偵測中...";

    analyzeTimer = setTimeout(async () => {
        const info = await eel.analyze_url(url)();
        
        // 更新 Badge
        const platforms = {
            'youtube': 'Youtube',
            'bilibili': 'Bilibili',
            'twitch': 'Twitch',
            'unknown': '未知平台'
        };
        
        let text = platforms[info.platform] || info.platform;
        if (info.is_live) text += " (LIVE)";
        
        badge.innerText = text;
        badge.style.color = info.platform === 'unknown' ? '#f38ba8' : '#a6e3a1';

        // 更新直播警告狀態
        detectedLive = info.is_live;
        const currentMode = document.querySelector('input[name="downloadMode"]:checked').value;
        checkLiveWarning(currentMode);

    }, 500); // 防抖動
}

function checkLiveWarning(mode) {
    const warningBox = document.getElementById('liveWarning');
    if (detectedLive && (mode === 'video' || mode === 'audio')) {
        warningBox.classList.remove('hidden');
    } else {
        warningBox.classList.add('hidden');
    }
}

// 開始下載
function startDownload() {
    const url = document.getElementById('urlInput').value.trim();
    if (!url) {
        alert("請輸入網址！");
        return;
    }

    // 收集選項
    const mode = document.querySelector('input[name="downloadMode"]:checked').value;
    const options = {
        mode: mode,
        is_live_mode: detectedLive,
        video_quality: document.getElementById('vid_quality').value,
        audio_quality: document.getElementById('aud_bitrate').value,
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

    // 重置介面
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('percentNum').innerText = '0%';
    document.getElementById('statusMsg').innerText = '準備中...';
    document.getElementById('logConsole').innerHTML = ''; // 清空 Log

    eel.start_download_task(url, options);
}

// Eel 接收函式
eel.expose(update_progress);
function update_progress(percent, msg) {
    document.getElementById('progressBar').style.width = percent + '%';
    document.getElementById('percentNum').innerText = Math.floor(percent) + '%';
    if (msg) document.getElementById('statusMsg').innerText = msg;
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