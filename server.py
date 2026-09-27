# -*- coding: utf-8 -*-
"""
《れじぇくろ！》輕量互動式劇情播放器 (Lite 雲端隨選回補版)
- 超輕量初始體積 (~190MB)
- 點擊角色時自動自官方 CDN 即時下載動畫、插圖、語音與劇本 (~10-15MB/回)
- 支援本機離線快取，玩過的角色永久保存在本地，越玩越完整
- 支援一鍵全量背景下載
"""

import os
import sys
import glob
import re
import json
import gzip
import shutil
import time
import wave
import struct
import subprocess
import mimetypes
import webbrowser
import socket
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.parse
import urllib.request
import concurrent.futures
import threading
import ssl
import types

# 提前定義執行環境目錄與 DLL 搜索路徑 (必須在 UnityPy / fmod 載入前完成)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    MEI_DIR = getattr(sys, '_MEIPASS', BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    MEI_DIR = BASE_DIR

# 設置 FMOD DLL 與 Windows DLL 目錄
_fmod_candidates = [
    os.path.join(MEI_DIR, 'fmod_toolkit', 'libfmod', 'Windows', 'x64', 'fmod.dll'),
    os.path.join(MEI_DIR, 'libfmod', 'Windows', 'x64', 'fmod.dll'),
    os.path.join(BASE_DIR, 'fmod.dll'),
    os.path.join(MEI_DIR, 'fmod.dll'),
    os.path.join(BASE_DIR, 'vgmstream', 'fmod.dll'),
]
for _fp in _fmod_candidates:
    if os.path.isfile(_fp):
        os.environ["PYFMODEX_DLL_PATH"] = _fp
        try:
            if hasattr(os, 'add_dll_directory'):
                os.add_dll_directory(os.path.dirname(_fp))
        except Exception:
            pass
        break

for _dir in [MEI_DIR, BASE_DIR]:
    if os.path.isdir(_dir):
        try:
            if hasattr(os, 'add_dll_directory'):
                os.add_dll_directory(_dir)
        except Exception:
            pass

# 徹底解決在無 CA 憑證環境或不同 Windows 電腦上的 SSL 驗證失敗問題
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

# 導入 UnityPy 與 fmod_toolkit 的雙重保護機制
try:
    import fmod_toolkit
except Exception:
    # 若在特殊系統環境下 FMOD 載入失敗，提供 stub 避免阻塞 UnityPy 核心解析
    mock_fmod = types.ModuleType('fmod_toolkit')
    mock_fmod.get_pyfmodex_system_instance = None
    mock_fmod.raw_to_wav = None
    mock_fmod.sound_to_wav = None
    mock_fmod.subsound_to_wav = None
    sys.modules['fmod_toolkit'] = mock_fmod

import imageio_ffmpeg
import UnityPy

# 強化 UnityPy.helpers.Tpk.get_typetree 容錯：若打包缺少 UnityPy.resources，自動由 MEI_DIR 或本地讀取 lzma.tpk
try:
    import UnityPy.helpers.Tpk as _Tpk
    _orig_get_typetree = _Tpk.get_typetree
    _cached_blob = None

    def _safe_get_typetree():
        global _cached_blob
        if _cached_blob is not None:
            return _cached_blob
        try:
            _cached_blob = _orig_get_typetree()
            return _cached_blob
        except Exception:
            # 備援嘗試從已知路徑手動解析 lzma.tpk
            for cand in [
                os.path.join(MEI_DIR, 'UnityPy', 'resources', 'lzma.tpk'),
                os.path.join(MEI_DIR, 'resources', 'lzma.tpk'),
                os.path.join(MEI_DIR, 'lzma.tpk'),
                os.path.join(BASE_DIR, 'lzma.tpk'),
                os.path.join(BASE_DIR, 'resources', 'lzma.tpk'),
                os.path.join(BASE_DIR, 'UnityPy', 'resources', 'lzma.tpk'),
            ]:
                if os.path.isfile(cand):
                    try:
                        from io import BytesIO
                        from tpk_ar import TpkFile
                        with open(cand, 'rb') as f:
                            _cached_blob = TpkFile.parse(BytesIO(f.read())).GetDataBlob()
                            return _cached_blob
                    except Exception:
                        pass
            raise
    _Tpk.get_typetree = _safe_get_typetree
except Exception:
    pass

# 防禦性確保 archspec 不會因遺漏 json 檔案而導致 Texture2D / astc 解碼失敗
try:
    import archspec.cpu
    _orig_host = archspec.cpu.host
    def _safe_host():
        try:
            return _orig_host()
        except Exception:
            class _DummyFamily:
                name = "x86_64"
            class _DummyHost:
                family = _DummyFamily()
                features = ["sse2", "sse4_1", "avx2"]
            return _DummyHost()
    archspec.cpu.host = _safe_host
except Exception:
    pass

def load_config():
    cfg = {
        "cdn_base": "https://asset-tw.legeclo.johren.games/pcr",
        "port": 8888,
        "auto_open_browser": True
    }
    cfg_file = os.path.join(BASE_DIR, 'config.json')
    example_file = os.path.join(BASE_DIR, 'config.example.json')
    target_file = cfg_file if os.path.isfile(cfg_file) else (example_file if os.path.isfile(example_file) else None)
    if target_file:
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"[!] 讀取配置檔 {target_file} 失敗: {e}")
    env_cdn = os.environ.get("LEGECLO_CDN_BASE")
    if env_cdn:
        cfg["cdn_base"] = env_cdn
    return cfg

CONFIG = load_config()
CDN_BASE = CONFIG.get("cdn_base", "https://asset-tw.legeclo.johren.games/pcr").rstrip('/')
PORT = int(CONFIG.get("port", 8888))
AUTO_OPEN = bool(CONFIG.get("auto_open_browser", True))

RESOURCE_DIR = os.path.join(BASE_DIR, 'resources')
CACHE_DIR = os.path.join(BASE_DIR, 'cache')
WEB_DIR = os.path.join(BASE_DIR, 'web')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
VGMSTREAM_EXE = os.path.join(BASE_DIR, 'vgmstream', 'vgmstream-cli.exe')

cand_ffmpeg = os.path.join(BASE_DIR, 'tools', 'ffmpeg.exe')
if os.path.exists(cand_ffmpeg):
    FFMPEG_EXE = cand_ffmpeg
elif os.path.exists(os.path.join(BASE_DIR, 'ffmpeg.exe')):
    FFMPEG_EXE = os.path.join(BASE_DIR, 'ffmpeg.exe')
else:
    try:
        import imageio_ffmpeg
        FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG_EXE = 'ffmpeg'

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(os.path.join(CACHE_DIR, 'bgm'), exist_ok=True)
os.makedirs(os.path.join(CACHE_DIR, 'standing'), exist_ok=True)
os.makedirs(os.path.join(CACHE_DIR, 'avatars'), exist_ok=True)

# 載入中繼資料與 CDN 清單
CHAR_NAME_CACHE = {}
names_file = os.path.join(BASE_DIR, 'char_names.json')
if os.path.exists(names_file):
    try:
        with open(names_file, 'r', encoding='utf-8') as f:
            CHAR_NAME_CACHE = json.load(f)
    except Exception:
        pass

CHAR_CATALOG = []
catalog_file = os.path.join(BASE_DIR, 'char_catalog.json')
if os.path.exists(catalog_file):
    try:
        with open(catalog_file, 'r', encoding='utf-8') as f:
            CHAR_CATALOG = json.load(f)
    except Exception:
        pass

CHAR_MODEL_MAP = {}
model_map_file = os.path.join(BASE_DIR, 'char_model_map.json')
if os.path.exists(model_map_file):
    try:
        with open(model_map_file, 'r', encoding='utf-8') as f:
            CHAR_MODEL_MAP = json.load(f)
    except Exception:
        pass

CDN_MANIFEST = {}
manifest_file = os.path.join(BASE_DIR, 'cdn_manifest.json')
if os.path.exists(manifest_file):
    try:
        with open(manifest_file, 'r', encoding='utf-8') as f:
            CDN_MANIFEST = json.load(f)
    except Exception:
        pass

ALIAS_MAP = {
    'richard_i1': 'richard_i',
    'claudette_legend': 'claudette',
    'khatia_legend': 'khatia',
}

def fetch_cdn_file(rel_path, local_path, optional=False, retries=3):
    """自 CDN 抓取檔案，自動處理 Gzip 解壓並存入指定路徑 (完全略過 SSL 驗證)"""
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return True
    url = f"{CDN_BASE}/{urllib.parse.quote(rel_path.replace(os.sep, '/'))}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=25, context=SSL_CTX) as resp:
                data = resp.read()
                if data.startswith(b'\x1f\x8b'):
                    try:
                        data = gzip.decompress(data)
                    except Exception:
                        pass
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'wb') as f:
                    f.write(data)
                return True
        except urllib.error.HTTPError as e:
            if not optional:
                print(f"[CDN] 遠端資源不存在 ({e.code}): {url}")
            return False
        except Exception as e:
            if attempt == retries - 1:
                if not optional:
                    print(f"[CDN] 下載失敗 {url}:", e)
                return False
            time.sleep(0.5)
    return False

def ensure_chapter_assets(cid, ep):
    """確保指定章節的所有動畫、插圖、劇本與語音資源已從 CDN 回補至本機"""
    if not CDN_MANIFEST:
        return
    
    alt_cid = ALIAS_MAP.get(cid, cid)
    char_entry = CDN_MANIFEST.get(cid) or CDN_MANIFEST.get(alt_cid, {})
    ep_entry = char_entry.get(str(ep))
    if not ep_entry:
        return

    tasks = []
    # 1. 劇本腳本
    sc_name = ep_entry.get('scenario')
    if sc_name:
        sc_local = os.path.join(RESOURCE_DIR, 'adv', 'scenario', sc_name)
        if not (os.path.exists(sc_local) and os.path.getsize(sc_local) > 0):
            tasks.append((f"adv/scenario/{sc_name}", sc_local))

    # 2. 動畫 USM
    for mo in ep_entry.get('movies', []):
        mo_local = os.path.join(RESOURCE_DIR, 'adv', 'movie', mo)
        if not (os.path.exists(mo_local) and os.path.getsize(mo_local) > 0):
            tasks.append((f"adv/movie/{mo}", mo_local))

    # 3. 插圖 CG
    for st in ep_entry.get('stills', []):
        st_local = os.path.join(RESOURCE_DIR, 'adv', 'still', st)
        if not (os.path.exists(st_local) and os.path.getsize(st_local) > 0):
            tasks.append((f"adv/still/{st}", st_local))

    # 4. 角色語音 ACB (WebGL 音訊)
    vc_name = ep_entry.get('voice')
    if vc_name:
        vc_local = os.path.join(RESOURCE_DIR, 'sound', 'adv', vc_name)
        if not (os.path.exists(vc_local) and os.path.getsize(vc_local) > 0):
            tasks.append((f"sound/webgl/adv/{vc_name}", vc_local))

    if tasks:
        print(f"[*] ☁️ 正在自 CDN 即時串流回補 {cid} 第 {ep} 話 ({len(tasks)} 個檔案)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(fetch_cdn_file, rel, loc) for rel, loc in tasks]
            concurrent.futures.wait(futures)
        print(f"[+] ✅ {cid} 第 {ep} 話資源回補完成！")

def get_char_name(cid):
    return CHAR_NAME_CACHE.get(cid, cid)

def ensure_avatar(cid):
    """即時提取並提供角色 256x256 高畫質大頭貼圖標"""
    out_dir = os.path.join(CACHE_DIR, 'avatars')
    os.makedirs(out_dir, exist_ok=True)
    out_png = os.path.join(out_dir, f"{cid}.png")
    if os.path.exists(out_png) and os.path.getsize(out_png) > 1000:
        return f"/cache/avatars/{cid}.png"

    # 若快取不存在，嘗試從仍保存在本地的 CG 截圖
    cand_stills = glob.glob(os.path.join(RESOURCE_DIR, 'adv', 'still', f'hs_{cid}_st_*.jpg'))
    if cand_stills:
        try:
            from PIL import Image
            env = UnityPy.load(cand_stills[0])
            for obj in env.objects:
                if obj.type.name == 'Texture2D':
                    img = obj.read().image
                    w, h = img.size
                    min_dim = min(w, h)
                    left = int(w * 0.3)
                    top = int(h * 0.1)
                    dim = int(min_dim * 0.6)
                    cropped = img.crop((left, top, left+dim, top+dim)).resize((256, 256), Image.LANCZOS)
                    cropped.save(out_png)
                    return f"/cache/avatars/{cid}.png"
        except Exception:
            pass

    return '/assets/default_avatar.png'

def get_all_characters():
    """獲取全部角色列表 (標註是否已下載本機快取)"""
    if CHAR_CATALOG:
        res = []
        movie_dir = os.path.join(RESOURCE_DIR, 'adv', 'movie')
        for item in CHAR_CATALOG:
            cid = item['id']
            mo_check = glob.glob(os.path.join(movie_dir, f'hs_{cid}_mo_*.usm.bytes'))
            c_copy = dict(item)
            c_copy['is_downloaded'] = len(mo_check) > 0
            res.append(c_copy)
        return res
    return []

def extract_usm(usm_path, out_mp4):
    """將 USM 容器內的 H.264 影像轉碼為標準 60fps MP4"""
    if os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 10000:
        return True
    try:
        env = UnityPy.load(usm_path)
        video_bytes = bytearray()
        for obj in env.objects:
            if obj.type.name == 'TextAsset':
                raw = obj.read().m_Script.encode('utf-8', 'surrogateescape')
                offset = 0
                while offset + 8 <= len(raw):
                    magic = raw[offset:offset+4]
                    size = struct.unpack('>I', raw[offset+4:offset+8])[0]
                    hdr_size = raw[offset+9] if offset+10 <= len(raw) else 0
                    if magic == b'@SFV':
                        frame_data = raw[offset+8+hdr_size : offset+8+size]
                        if frame_data.startswith(b'\x00\x00\x01'):
                            video_bytes.extend(frame_data)
                    offset += 8 + size
                break
        if not video_bytes: return False
        tmp_m2v = out_mp4 + '.m2v'
        with open(tmp_m2v, 'wb') as f:
            f.write(video_bytes)
        cmd = [FFMPEG_EXE, '-y', '-i', tmp_m2v, '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-r', '60', '-pix_fmt', 'yuv420p', out_mp4]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(tmp_m2v): os.remove(tmp_m2v)
        return os.path.exists(out_mp4)
    except Exception as e:
        print(f"USM 提取失敗 {usm_path}:", e)
        return False

def extract_still(still_path, out_png):
    """提取劇照插圖 (Texture2D) 為 PNG"""
    if os.path.exists(out_png) and os.path.getsize(out_png) > 10000:
        return True
    try:
        env = UnityPy.load(still_path)
        for obj in env.objects:
            if obj.type.name == 'Texture2D':
                obj.read().image.save(out_png)
                return True
    except Exception as e:
        print(f"CG 提取失敗 {still_path}:", e)
    return False

def extract_acb_voices(acb_path, out_dir):
    """解碼角色劇本語音庫 (AFS2/AAC/HCA -> WAV)"""
    if os.path.exists(out_dir) and len(os.listdir(out_dir)) > 5:
        return True
    os.makedirs(out_dir, exist_ok=True)
    
    # 提取內嵌 ACB 音訊
    tmp_acb = os.path.join(out_dir, 'raw.acb')
    if not (os.path.exists(tmp_acb) and os.path.getsize(tmp_acb) > 0):
        try:
            env = UnityPy.load(acb_path)
            for obj in env.objects:
                if obj.type.name == 'TextAsset':
                    raw = obj.read().m_Script.encode('utf-8', 'surrogateescape')
                    with open(tmp_acb, 'wb') as f:
                        f.write(raw)
                    break
        except Exception:
            return False

    if not os.path.exists(tmp_acb): return False

    if os.path.exists(VGMSTREAM_EXE):
        out_pattern = os.path.join(out_dir, 'v_?s.wav')
        cmd = [VGMSTREAM_EXE, '-s', '1', '-S', '0', '-o', out_pattern, tmp_acb]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 依 subsong 編號重命名為 4 位數格式
        extracted_wavs = sorted(glob.glob(os.path.join(out_dir, 'v_*.wav')))
        for w in extracted_wavs:
            bn = os.path.basename(w)
            m = re.match(r'v_(\d+)\.wav', bn)
            if m:
                idx = int(m.group(1)) - 1
                new_name = os.path.join(out_dir, f'v_{idx:04d}.wav')
                if w != new_name and not os.path.exists(new_name):
                    try: os.rename(w, new_name)
                    except Exception: pass
        if os.path.exists(tmp_acb):
            try: os.remove(tmp_acb)
            except Exception: pass
        return len(glob.glob(os.path.join(out_dir, 'v_*.wav'))) > 0
    return False

def ensure_bgm(bgm_name):
    """取得背景音樂音訊 (WAV 串流)"""
    out_wav = os.path.join(CACHE_DIR, 'bgm', f"{bgm_name}.wav")
    if os.path.exists(out_wav) and os.path.getsize(out_wav) > 10000:
        return f"/cache/bgm/{bgm_name}.wav"

    # 若快取不存在，自 CDN 回補該首 BGM
    bgm_local = os.path.join(RESOURCE_DIR, 'sound', 'webgl', 'bgm', f"{bgm_name}.acb.bytes")
    if not (os.path.exists(bgm_local) and os.path.getsize(bgm_local) > 0):
        fetch_cdn_file(f"sound/webgl/bgm/{bgm_name}.acb.bytes", bgm_local)

    if os.path.exists(bgm_local):
        try:
            env = UnityPy.load(bgm_local)
            tmp_acb = out_wav + '.acb'
            for obj in env.objects:
                if obj.type.name == 'TextAsset':
                    raw = obj.read().m_Script.encode('utf-8', 'surrogateescape')
                    with open(tmp_acb, 'wb') as f:
                        f.write(raw)
                    break
            if os.path.exists(tmp_acb) and os.path.exists(VGMSTREAM_EXE):
                cmd = [VGMSTREAM_EXE, '-o', out_wav, tmp_acb]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(tmp_acb): os.remove(tmp_acb)
                if os.path.exists(out_wav):
                    return f"/cache/bgm/{bgm_name}.wav"
        except Exception:
            pass

    # 預設保底 BGM
    cand_asset = os.path.join(ASSETS_DIR, f"{bgm_name}.wav")
    if os.path.exists(cand_asset):
        return f"/assets/{bgm_name}.wav"
    cand_default = os.path.join(ASSETS_DIR, 'bgm_scene_0005.wav')
    if os.path.exists(cand_default):
        return '/assets/bgm_scene_0005.wav'
    return None

def ensure_background(bg_name, cid, ep_str):
    """取得場景背景圖片 (自 CDN 回補或保底預設)"""
    if not bg_name:
        return '/assets/default_bg.png'
    out_png = os.path.join(CACHE_DIR, f"{cid}_{ep_str}", f"{bg_name}.png")
    if os.path.exists(out_png):
        return f"/cache/{cid}_{ep_str}/{bg_name}.png"

    # 嘗試從 CDN 回補 (背景為可選素材，靜默嘗試)
    bg_local = os.path.join(RESOURCE_DIR, 'adv', 'background', f"{bg_name}.png")
    if not (os.path.exists(bg_local) and os.path.getsize(bg_local) > 0):
        fetch_cdn_file(f"adv/background/{bg_name}.png", bg_local, optional=True)

    if os.path.exists(bg_local):
        extract_still(bg_local, out_png)
        if os.path.exists(out_png):
            return f"/cache/{cid}_{ep_str}/{bg_name}.png"
    return '/assets/default_bg.png'

def ensure_standing(cid):
    """即時提取並提供角色 Spine 2D 骨骼動態立繪 (若缺少則自 CDN 回補)"""
    out_dir = os.path.join(CACHE_DIR, 'standing', cid)
    os.makedirs(out_dir, exist_ok=True)
    atlas_out = os.path.join(out_dir, 'standing.atlas')
    skel_out = os.path.join(out_dir, 'standing.skel')
    info_json = os.path.join(out_dir, 'info.json')

    if os.path.exists(info_json) and os.path.exists(atlas_out) and os.path.exists(skel_out):
        try:
            with open(info_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    alt_cid = ALIAS_MAP.get(cid, cid)
    model_info = CHAR_MODEL_MAP.get(cid) or CHAR_MODEL_MAP.get(alt_cid)

    if model_info:
        folder = model_info['folder']
        prefix = model_info['prefix']
        export_dir = os.path.join(RESOURCE_DIR, 'characters', folder, 'avatar', 'standing', 'export')
        atlas_bundle = os.path.join(export_dir, f"{prefix}.atlas.txt")
        skel_bundle = os.path.join(export_dir, f"{prefix}.skel.bytes")
        mat_bundle = os.path.join(export_dir, f"{prefix}_material.mat")

        dl_tasks = []
        if not (os.path.exists(atlas_bundle) and os.path.getsize(atlas_bundle) > 0):
            dl_tasks.append((f"characters/{folder}/avatar/standing/export/{prefix}.atlas.txt", atlas_bundle))
        if not (os.path.exists(skel_bundle) and os.path.getsize(skel_bundle) > 0):
            dl_tasks.append((f"characters/{folder}/avatar/standing/export/{prefix}.skel.bytes", skel_bundle))
        if not (os.path.exists(mat_bundle) and os.path.getsize(mat_bundle) > 0):
            dl_tasks.append((f"characters/{folder}/avatar/standing/export/{prefix}_material.mat", mat_bundle))

        if dl_tasks:
            print(f"[*] ☁️ 正在自 CDN 回補 {cid} 立繪骨骼模型 ({len(dl_tasks)} 個檔案)...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(fetch_cdn_file, rel, loc) for rel, loc in dl_tasks]
                concurrent.futures.wait(futures)

        if os.path.exists(skel_bundle) and os.path.exists(mat_bundle):
            try:
                # 1. 提取 Atlas
                env_atlas = UnityPy.load(atlas_bundle)
                for obj in env_atlas.objects:
                    if obj.type.name == 'TextAsset':
                        raw_atlas = obj.read().m_Script.encode('utf-8', 'surrogateescape')
                        clean_text = raw_atlas.decode('utf-8', errors='ignore').strip() + '\n'
                        with open(atlas_out, 'w', encoding='utf-8', newline='\n') as f:
                            f.write(clean_text)
                        break

                # 2. 提取 Skel
                anims = []
                env_skel = UnityPy.load(skel_bundle)
                for obj in env_skel.objects:
                    if obj.type.name == 'TextAsset':
                        raw_skel = obj.read().m_Script.encode('utf-8', 'surrogateescape')
                        with open(skel_out, 'wb') as f:
                            f.write(raw_skel)
                        canonical = ['st_01_standard', 'st_02_normal', 'st_03_smile', 'st_04_anger',
                                     'st_05_sad', 'st_06_shy', 'st_07_surprise', 'st_08_stop',
                                     'st_09_sp01', 'st_10_sp02', 'st_11_sp03', 'st_12_sp04', 'st_13_sp05']
                        anims = [a for a in canonical if a.encode('latin1') in raw_skel]
                        if not anims:
                            anims = sorted(list(set(s.decode('latin1') for s in re.findall(rb'st_\d\d_[a-zA-Z_]+', raw_skel))))
                        break

                # 3. 提取 Material
                png_name = f'{prefix}.png'
                env_mat = UnityPy.load(mat_bundle)
                for obj in env_mat.objects:
                    if obj.type.name == 'Texture2D':
                        img = obj.read().image
                        try:
                            with open(atlas_out, 'r', encoding='utf-8', errors='ignore') as af:
                                m = re.search(r'size:\s*(\d+)\s*,\s*(\d+)', af.read())
                                if m:
                                    tw, th = int(m.group(1)), int(m.group(2))
                                    if img.size != (tw, th):
                                        from PIL import Image
                                        img = img.resize((tw, th), Image.Resampling.LANCZOS)
                        except Exception:
                            pass
                        img.save(os.path.join(out_dir, png_name))
                        break

                avatar_fallback = f'/cache/avatars/{cid}_half.png' if os.path.exists(os.path.join(CACHE_DIR, 'avatars', f"{cid}_half.png")) else f'/cache/avatars/{cid}.png'
                info = {
                    'has_standing': True,
                    'character_id': cid,
                    'atlas': f'/cache/standing/{cid}/standing.atlas',
                    'skel': f'/cache/standing/{cid}/standing.skel',
                    'png': f'/cache/standing/{cid}/{png_name}',
                    'fallback_img': avatar_fallback,
                    'animations': anims if anims else ['st_01_standard', 'st_02_normal', 'st_03_smile', 'st_04_anger', 'st_05_sad', 'st_06_shy', 'st_07_surprise'],
                    'default_anim': 'st_01_standard' if 'st_01_standard' in anims else (anims[0] if anims else 'st_01_standard')
                }
                with open(info_json, 'w', encoding='utf-8') as f:
                    json.dump(info, f, ensure_ascii=False)
                return info
            except Exception as e:
                print(f"[!] ensure_standing {cid} 錯誤:", e)

    avatar_path = f"/cache/avatars/{cid}_half.png" if os.path.exists(os.path.join(CACHE_DIR, 'avatars', f"{cid}_half.png")) else f"/cache/avatars/{cid}.png"
    return {'has_standing': False, 'character_id': cid, 'fallback_img': avatar_path}

def get_chapter_data(cid, ep):
    """解析並回傳章節、動作段落、音訊與劇本資料 (自動回補)"""
    ep_str = f"{int(ep):02d}"
    char_cache = os.path.join(CACHE_DIR, f"{cid}_{ep_str}")
    os.makedirs(char_cache, exist_ok=True)

    alt_cid = ALIAS_MAP.get(cid, cid)

    # 1. 確保章節素材已自 CDN 回補
    ensure_chapter_assets(cid, ep)

    # 2. 動畫段落轉碼
    mo_files = sorted(glob.glob(os.path.join(RESOURCE_DIR, 'adv', 'movie', f'hs_{cid}_mo_{ep_str}*.usm.bytes')))
    if not mo_files and alt_cid != cid:
        mo_files = sorted(glob.glob(os.path.join(RESOURCE_DIR, 'adv', 'movie', f'hs_{alt_cid}_mo_{ep_str}*.usm.bytes')))
    movie_list = []
    for mf in mo_files:
        mid = os.path.basename(mf).replace('.usm.bytes', '')
        mout = os.path.join(char_cache, f'{mid}.mp4')
        extract_usm(mf, mout)
        if os.path.exists(mout):
            movie_list.append({
                'id': mid,
                'url': f'/cache/{cid}_{ep_str}/{mid}.mp4'
            })

    # 3. 插圖 CG 提取
    st_files = sorted(glob.glob(os.path.join(RESOURCE_DIR, 'adv', 'still', f'hs_{cid}_st_{ep_str}*.jpg')))
    if not st_files and alt_cid != cid:
        st_files = sorted(glob.glob(os.path.join(RESOURCE_DIR, 'adv', 'still', f'hs_{alt_cid}_st_{ep_str}*.jpg')))
    still_list = []
    for sf in st_files:
        sid = os.path.basename(sf).replace('.jpg', '')
        sout = os.path.join(char_cache, f'{sid}.png')
        extract_still(sf, sout)
        if os.path.exists(sout):
            still_list.append({
                'id': sid,
                'url': f'/cache/{cid}_{ep_str}/{sid}.png'
            })

    # 4. 角色語音解碼
    acb_file = os.path.join(RESOURCE_DIR, 'sound', 'adv', f'cs_{cid}_{ep_str}.acb.bytes')
    if not os.path.exists(acb_file) and alt_cid != cid:
        acb_file = os.path.join(RESOURCE_DIR, 'sound', 'adv', f'cs_{alt_cid}_{ep_str}.acb.bytes')
    has_voice = os.path.exists(acb_file)
    voice_dir = os.path.join(char_cache, 'voices')
    if has_voice:
        extract_acb_voices(acb_file, voice_dir)

    # 5. 解析劇本腳本
    sc_file = os.path.join(RESOURCE_DIR, 'adv', 'scenario', f'cs_{cid}_{ep_str}.evsc.bytes')
    if not os.path.exists(sc_file) and alt_cid != cid:
        sc_file = os.path.join(RESOURCE_DIR, 'adv', 'scenario', f'cs_{alt_cid}_{ep_str}.evsc.bytes')
    entries = []
    if os.path.exists(sc_file):
        try:
            env = UnityPy.load(sc_file)
            for obj in env.objects:
                if obj.type.name == 'TextAsset':
                    raw = obj.read().m_Script.encode('utf-8', 'surrogateescape')
                    pos = 2000
                    while pos < len(raw):
                        end = raw.find(b'\x00', pos)
                        if end == -1: break
                        chunk = raw[pos:end]
                        try:
                            s = chunk.decode('utf-8')
                            if s and not s.isdigit() and len(s) > 1:
                                entries.append(s)
                        except Exception:
                            pass
                        pos = end + 1
        except Exception as e:
            print("解析劇本失敗:", e)

    # 剔除檔案開頭預宣告區塊
    first_d_idx = -1
    for idx_e, e_item in enumerate(entries):
        if any('\u4e00' <= c <= '\u9fff' for c in e_item) and len(e_item) > 2:
            first_d_idx = idx_e
            break

    if first_d_idx > 0:
        last_manifest = -1
        for idx_e in range(first_d_idx):
            if ('_mo_' in entries[idx_e] or '_st_' in entries[idx_e]) and entries[idx_e].startswith('hs_'):
                last_manifest = idx_e
        if last_manifest != -1:
            entries = entries[last_manifest + 1:]

    # 尋找背景與 BGM
    bg_name = None
    bgm_name = None
    for e in entries:
        if not bg_name and e.startswith('ab_') and not e.startswith(('ab_997', 'ab_998')):
            bg_name = e
        if not bgm_name and e.startswith('bgm_'):
            bgm_name = e
        if bg_name and bgm_name:
            break

    bg_url = ensure_background(bg_name, cid, ep_str)
    bgm_url = ensure_bgm(bgm_name or 'bgm_scene_0005')

    # 建構視覺動作段落（Phase）
    phases = []
    phase_lookup = {}

    standing = ensure_standing(cid)

    # Phase 0: 場景背景與角色立繪
    phases.append({
        'id': bg_name or 'bg',
        'type': 'bg',
        'name': '場景背景與立繪',
        'url': bg_url,
        'standing': standing
    })
    if bg_name:
        phase_lookup[bg_name] = 0

    for e in entries:
        if e.startswith('ab_') and e not in phase_lookup:
            phase_lookup[e] = 0

    # Phase 1: 前置插圖
    if still_list:
        phase_lookup[still_list[0]['id']] = len(phases)
        phases.append({
            'id': still_list[0]['id'],
            'type': 'image',
            'name': '前置插圖',
            'url': still_list[0]['url']
        })

    # Phase 2..N: 60fps 動畫迴圈
    for idx, mo in enumerate(movie_list, 1):
        phase_lookup[mo['id']] = len(phases)
        phases.append({
            'id': mo['id'],
            'type': 'video',
            'name': f'動畫第 {idx} 段',
            'url': mo['url']
        })

    # Phase N+1: 結尾插圖
    if len(still_list) > 1:
        phase_lookup[still_list[1]['id']] = len(phases)
        phases.append({
            'id': still_list[1]['id'],
            'type': 'image',
            'name': '結尾插圖',
            'url': still_list[1]['url']
        })

    # 解析對白與同步
    dialogues = []
    curr_phase_idx = 0
    v_idx = 0
    i = 0
    while i < len(entries):
        token = entries[i]
        for pid, pidx in phase_lookup.items():
            if pid in token:
                curr_phase_idx = pidx
                break

        if any('\u4e00' <= c <= '\u9fff' for c in token) and len(token) > 1:
            speaker = ""
            text = token
            if i + 1 < len(entries):
                next_token = entries[i+1]
                if any('\u4e00' <= c <= '\u9fff' for c in next_token) and len(token) <= 8 and len(next_token) > len(token):
                    speaker = token
                    text = next_token
                    i += 1

            voice_url = None
            if has_voice:
                # 尋找該對白緊隨的語音標籤 (voice_..._XXXX_XX)
                voice_file = None
                for lookahead in range(1, 5):
                    if i + lookahead < len(entries):
                        t = entries[i + lookahead]
                        # 若下一個 token 已經是下一段中文對話，則停止向前搜尋
                        if any('\u4e00' <= c <= '\u9fff' for c in t) and len(t) > 2:
                            break
                        m = re.search(r'voice_.*?_(\d{4})_\d{2}', t)
                        if m:
                            v_num = int(m.group(1)) - 1
                            voice_file = f'v_{v_num:04d}.wav'
                            break

                if voice_file:
                    v_path = os.path.join(voice_dir, voice_file)
                    if os.path.exists(v_path):
                        voice_url = f'/cache/{cid}_{ep_str}/voices/{voice_file}'
                        v_idx = max(v_idx, v_num + 1)
                elif speaker:
                    # 容錯備援：若無明確 voice_ 標籤但確定為角色發言（非旁白），才按序檢查音訊
                    expected_wav = os.path.join(voice_dir, f'v_{v_idx:04d}.wav')
                    if os.path.exists(expected_wav):
                        voice_url = f'/cache/{cid}_{ep_str}/voices/v_{v_idx:04d}.wav'
                        v_idx += 1

            dialogues.append({
                'speaker': speaker,
                'text': text,
                'voice': voice_url,
                'phase_idx': curr_phase_idx
            })
        i += 1

    res_data = {
        'char_id': cid,
        'character_name': get_char_name(cid),
        'ep': ep_str,
        'title': f'{get_char_name(cid)} 第 {ep_str} 話',
        'bg_url': bg_url,
        'bgm_url': bgm_url,
        'phases': phases,
        'dialogues': dialogues,
        'standing': standing
    }
    try:
        with open(os.path.join(char_cache, 'chapter_data.json'), 'w', encoding='utf-8') as f:
            json.dump(res_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] 保存 chapter_data.json 失敗: {e}")
    return res_data

class LegecloHandler(SimpleHTTPRequestHandler):
    """輕量 HTTP 服務處理程序"""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 角色清單 API
        if path == '/api/characters':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            chars = get_all_characters()
            self.wfile.write(json.dumps(chars, ensure_ascii=False).encode('utf-8'))
            return
            
        # 章節詳細資料 API (觸發自動回補)
        if path == '/api/chapter':
            cid = query.get('char', ['tsukuyomi_wedding'])[0]
            ep = query.get('ep', ['3'])[0]
            data = get_chapter_data(cid, ep)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
            return

        # 快取重建/清理 API
        if path == '/api/clear_cache':
            cid = query.get('char', [''])[0]
            ctype = query.get('type', ['standing'])[0]

            if not cid:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"ok": false, "error": "Missing char parameter"}')
                return

            result = {'ok': True, 'cleared': []}
            if cid == 'all':
                standing_dir = os.path.join(CACHE_DIR, 'standing')
                if os.path.exists(standing_dir):
                    shutil.rmtree(standing_dir, ignore_errors=True)
                    os.makedirs(standing_dir, exist_ok=True)
                    result['cleared'].append('all_standing')
                print("[Cache] All standing caches purged.")
            else:
                char_standing_dir = os.path.join(CACHE_DIR, 'standing', cid)
                if os.path.exists(char_standing_dir):
                    shutil.rmtree(char_standing_dir, ignore_errors=True)
                    result['cleared'].append(f'standing_{cid}')
                    print(f"[Cache] Purged standing cache for {cid}.")

                if ctype in ('all', 'chapter'):
                    for item in os.listdir(CACHE_DIR):
                        if item.startswith(f"{cid}_"):
                            target = os.path.join(CACHE_DIR, item)
                            if os.path.isdir(target):
                                shutil.rmtree(target, ignore_errors=True)
                                result['cleared'].append(item)
                            elif os.path.isfile(target):
                                try:
                                    os.remove(target)
                                    result['cleared'].append(item)
                                except Exception:
                                    pass

                try:
                    new_standing = ensure_standing(cid)
                    result['standing'] = new_standing
                except Exception as e:
                    result['standing_error'] = str(e)
                    print(f"[Cache] Error re-extracting standing for {cid}: {e}")

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))
            return

        # 靜態資源串流 (/cache, /assets)
        if path.startswith('/cache/'):
            fpath = os.path.join(CACHE_DIR, path[7:].replace('/', os.sep))
            if not os.path.exists(fpath):
                if '_half.png' in fpath:
                    cand = fpath.replace('_half.png', '.png')
                    if os.path.exists(cand):
                        fpath = cand
                elif path.startswith('/cache/avatars/'):
                    fpath = os.path.join(ASSETS_DIR, 'default_avatar.png')
            if os.path.exists(fpath) and os.path.isfile(fpath):
                self.serve_file(fpath)
                return

        if path.startswith('/assets/'):
            fpath = os.path.join(ASSETS_DIR, path[8:].replace('/', os.sep))
            if os.path.exists(fpath) and os.path.isfile(fpath):
                self.serve_file(fpath)
                return

        # 前端靜態頁面
        if path == '/' or path == '':
            file_path = os.path.join(WEB_DIR, 'index.html')
        else:
            file_path = os.path.join(WEB_DIR, path.lstrip('/'))

        if os.path.exists(file_path) and os.path.isfile(file_path):
            self.serve_file(file_path)
        else:
            self.send_error(404, "File not found")

    def serve_file(self, file_path):
        """支援 HTTP 206 範圍請求的媒體檔案串流處理"""
        mime, _ = mimetypes.guess_type(file_path)
        if not mime:
            if file_path.endswith('.mp4'): mime = 'video/mp4'
            elif file_path.endswith('.wav'): mime = 'audio/wav'
            elif file_path.endswith('.png'): mime = 'image/png'
            elif file_path.endswith('.css'): mime = 'text/css'
            elif file_path.endswith('.js'): mime = 'application/javascript'
            elif file_path.endswith('.atlas'): mime = 'text/plain; charset=utf-8'
            elif file_path.endswith('.skel'): mime = 'application/octet-stream'
            elif file_path.endswith('.json'): mime = 'application/json; charset=utf-8'
            else: mime = 'application/octet-stream'

        try:
            file_size = os.path.getsize(file_path)
            range_header = self.headers.get('Range', None)
            
            if range_header:
                m = re.match(r'bytes=(\d+)-(\d*)', range_header)
                if m:
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else file_size - 1
                    end = min(end, file_size - 1)
                    length = end - start + 1
                    
                    self.send_response(206)
                    self.send_header('Content-Type', mime)
                    self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                    self.send_header('Content-Length', str(length))
                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    
                    with open(file_path, 'rb') as f:
                        f.seek(start)
                        chunk_size = 64 * 1024
                        bytes_left = length
                        while bytes_left > 0:
                            chunk = f.read(min(chunk_size, bytes_left))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            bytes_left -= len(chunk)
                    return

            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Access-Control-Allow-Origin', '*')
            if file_path.endswith('.html') or file_path.endswith('.js') or file_path.endswith('.css') or file_path.endswith('.json') or file_path.endswith('.atlas') or file_path.endswith('.skel'):
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            with open(file_path, 'rb') as f:
                chunk_size = 64 * 1024
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except Exception:
            pass

    def do_POST(self):
        """支援 POST 方法（與 GET 邏輯共用）"""
        return self.do_GET()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def find_available_port(start_port=8888, max_attempts=20):
    for p in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', p))
                return p
        except OSError:
            continue
    return start_port

def run_server(port=8888, open_browser=True):
    port = find_available_port(port)
    server_address = ('', port)
    httpd = ThreadedHTTPServer(server_address, LegecloHandler)
    url = f"http://localhost:{port}/"
    print("=" * 60)
    print("✨ 《れじぇくろ！》輕量互動劇情引擎 (Lite 雲端隨選版) 已啟動！")
    print(f"👉 請在瀏覽器中開啟：{url}")
    print("☁️ 點選任意角色將自動連線 CDN 即時回補資源")
    print("💡 請保持此視窗開啟，關閉此視窗將停止播放器伺服器")
    print("=" * 60)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n伺服器已停止。")

def batch_transcode_all(max_workers=4):
    print("=" * 65)
    print("🚀 啟動全量快取批次轉碼 (生成 ready-to-play 本機與手機完全離線快取)")
    print("=" * 65)
    
    # 1. 處理角色立繪 (Spine 骨骼與貼圖)
    print("[*] 正在處理角色立繪 (Spine 骨骼與貼圖)...")
    m_map = CHAR_MODEL_MAP
    if not m_map:
        model_map_file = os.path.join(BASE_DIR, 'char_model_map.json')
        if os.path.exists(model_map_file):
            try:
                with open(model_map_file, 'r', encoding='utf-8') as f:
                    m_map = json.load(f)
            except Exception:
                pass
    m_count = 0
    if m_map:
        for cid, m_info in m_map.items():
            folder = m_info.get('folder')
            pfx = m_info.get('prefix')
            if not folder or not pfx:
                continue
            skel = os.path.join(RESOURCE_DIR, 'characters', folder, 'avatar', 'standing', 'export', f"{pfx}.skel.bytes")
            if os.path.exists(skel):
                try:
                    ensure_standing(cid)
                    m_count += 1
                except Exception:
                    pass
    print(f"[+] 立繪處理完成：共處理 {m_count} 位角色")

    # 2. 搜尋 resources 內所有現存劇本/章節
    manifest = CDN_MANIFEST
    if not manifest:
        manifest_file = os.path.join(BASE_DIR, 'cdn_manifest.json')
        if os.path.exists(manifest_file):
            try:
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
            except Exception:
                pass

    all_tasks = []
    if manifest:
        for cid, eps in manifest.items():
            for ep in eps:
                ep_str = f"{int(ep):02d}"
                sc_file = os.path.join(RESOURCE_DIR, 'adv', 'scenario', f'cs_{cid}_{ep_str}.evsc.bytes')
                mo_files = glob.glob(os.path.join(RESOURCE_DIR, 'adv', 'movie', f'hs_{cid}_mo_{ep_str}*.usm.bytes'))
                if os.path.exists(sc_file) or len(mo_files) > 0:
                    all_tasks.append((cid, str(int(ep))))
    else:
        sc_files = glob.glob(os.path.join(RESOURCE_DIR, 'adv', 'scenario', 'cs_*.evsc.bytes'))
        for sc in sc_files:
            fn = os.path.basename(sc).replace('cs_', '').replace('.evsc.bytes', '')
            if '_' in fn:
                parts = fn.rsplit('_', 1)
                if len(parts) == 2 and parts[1].isdigit():
                    all_tasks.append((parts[0], str(int(parts[1]))))

    # 去重
    all_tasks = sorted(list(set(all_tasks)))

    total = len(all_tasks)
    print(f"[*] 檢測到已下載素材章節: {total} 個")
    if total == 0:
        print("[!] resources/ 目錄內未發現已下載的章節素材，請先執行回補下載！")
        return

    # 檢查哪些已經完整轉碼 (含 chapter_data.json)
    need_transcode = []
    already_cached = 0
    for cid, ep in all_tasks:
        ep_str = f"{int(ep):02d}"
        c_json = os.path.join(CACHE_DIR, f"{cid}_{ep_str}", 'chapter_data.json')
        if os.path.exists(c_json) and os.path.getsize(c_json) > 100:
            already_cached += 1
        else:
            need_transcode.append((cid, ep))

    print(f"[*] 快取現狀: 已轉碼 {already_cached} 個 | 待轉碼 {len(need_transcode)} 個")
    if not need_transcode:
        print("🎉 所有已下載章節皆已轉碼完成，快取已是最新狀態！")
        return

    print(f"[*] 開始平行轉碼 (啟用 {max_workers} 線程)...")
    start_t = time.time()
    done_cnt = 0
    err_cnt = 0

    def _worker(task):
        cid, ep = task
        try:
            get_chapter_data(cid, ep)
            return True, cid, ep, ""
        except Exception as e:
            return False, cid, ep, str(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_worker, t) for t in need_transcode]
        for fut in concurrent.futures.as_completed(futures):
            done_cnt += 1
            ok, cid, ep, err = fut.result()
            if not ok:
                err_cnt += 1
            pct = (done_cnt / len(need_transcode)) * 100
            elapsed = time.time() - start_t
            speed = done_cnt / elapsed if elapsed > 0 else 0
            cname = get_char_name(cid)
            print(f"\r[*] 進度: {done_cnt}/{len(need_transcode)} ({pct:.1f}%) | 正在處理: {cname} 第 {int(ep):02d} 話 | 速度: {speed:.1f} 話/秒", end="", flush=True)

    print()
    print("=" * 65)
    print(f"🎉 批次轉碼作業完成！成功: {done_cnt - err_cnt} 個 | 失敗: {err_cnt} 個 | 總耗時: {time.time()-start_t:.1f} 秒")
    print(f"📁 快取輸出目錄: {CACHE_DIR}")
    print("📱 您現在可以執行 sync_cache_to_phone 將完整快取同步到手機！")
    print("=" * 65)

if __name__ == '__main__':
    if '--transcode' in sys.argv or '--batch-transcode' in sys.argv:
        batch_transcode_all()
        sys.exit(0)
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else PORT
    run_server(port, open_browser=AUTO_OPEN)
