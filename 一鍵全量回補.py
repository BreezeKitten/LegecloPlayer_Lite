# -*- coding: utf-8 -*-
"""
《れじぇくろ！》輕量版 - 一鍵全量資源回補工具 (Bulk Asset Downloader)
- 支援斷點續傳 (已下載檔案自動跳過)
- 內建 SSL 容錯穿透 (任何電腦皆可穩定連線)
- 支援多線程極速平行下載
- 支援分組回補 (立繪/劇本/語音/全量)
"""

import os
import sys
import json
import gzip
import time
import ssl
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_config():
    cfg = {"cdn_base": "https://asset-tw.legeclo.johren.games/pcr"}
    cfg_file = os.path.join(BASE_DIR, 'config.json')
    example_file = os.path.join(BASE_DIR, 'config.example.json')
    target_file = cfg_file if os.path.isfile(cfg_file) else (example_file if os.path.isfile(example_file) else None)
    if target_file:
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    env_cdn = os.environ.get("LEGECLO_CDN_BASE")
    if env_cdn:
        cfg["cdn_base"] = env_cdn
    return cfg

CONFIG = load_config()
CDN_BASE = CONFIG.get("cdn_base", "https://asset-tw.legeclo.johren.games/pcr").rstrip('/')
RESOURCE_DIR = os.path.join(BASE_DIR, 'resources')

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

def fetch_file(rel_path, local_path, retries=3):
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return True, "skipped"
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
                return True, "downloaded"
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return False, f"HTTP {e.code}"
        except Exception as e:
            if attempt == retries - 1:
                return False, str(e)
            time.sleep(0.5)
    return False, "failed"

def main():
    print("=" * 65)
    print("✨ 《れじぇくろ！》輕量版 - 一鍵全量資源回補工具 ✨")
    print("=" * 65)
    print()

    manifest_path = os.path.join(BASE_DIR, 'cdn_manifest.json')
    model_map_path = os.path.join(BASE_DIR, 'char_model_map.json')

    if not os.path.exists(manifest_path):
        print("[錯誤] 找不到 cdn_manifest.json 清單檔案！")
        input("\n按 Enter 鍵結束...")
        return

    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    model_map = {}
    if os.path.exists(model_map_path):
        with open(model_map_path, 'r', encoding='utf-8') as f:
            model_map = json.load(f)

    # 分類建立工作任務
    tasks_scenario = []
    tasks_standing = []
    tasks_voice = []
    tasks_still = []
    tasks_movie = []

    # 1. 立繪
    for cid, m_info in model_map.items():
        folder = m_info['folder']
        pfx = m_info['prefix']
        exp_dir = os.path.join(RESOURCE_DIR, 'characters', folder, 'avatar', 'standing', 'export')
        for ext in ['.atlas.txt', '.skel.bytes', '_material.mat']:
            tasks_standing.append((
                f"characters/{folder}/avatar/standing/export/{pfx}{ext}",
                os.path.join(exp_dir, f"{pfx}{ext}")
            ))

    # 2. 劇本、動畫、插圖、語音
    for cid, eps in manifest.items():
        for ep, data in eps.items():
            sc = data.get('scenario')
            if sc:
                tasks_scenario.append((f"adv/scenario/{sc}", os.path.join(RESOURCE_DIR, 'adv', 'scenario', sc)))
            vc = data.get('voice')
            if vc:
                tasks_voice.append((f"sound/webgl/adv/{vc}", os.path.join(RESOURCE_DIR, 'sound', 'adv', vc)))
            for st in data.get('stills', []):
                tasks_still.append((f"adv/still/{st}", os.path.join(RESOURCE_DIR, 'adv', 'still', st)))
            for mo in data.get('movies', []):
                tasks_movie.append((f"adv/movie/{mo}", os.path.join(RESOURCE_DIR, 'adv', 'movie', mo)))

def safe_input(prompt, default=""):
    try:
        val = input(prompt).strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        return default

def run_transcode():
    """執行快取批次轉碼 (支援 server.py 或 啟動播放器.exe)"""
    print("\n" + "=" * 65)
    print("🚀 正在啟動快取批次轉碼模組...")
    print("=" * 65)
    
    server_py = os.path.join(BASE_DIR, 'server.py')
    exe_cand = os.path.join(BASE_DIR, '啟動播放器.exe')
    
    # 1. 優先透過 python 執行 server.py
    if os.path.exists(server_py):
        py_exec = sys.executable if not getattr(sys, 'frozen', False) else 'python'
        try:
            res = subprocess.run([py_exec, server_py, '--transcode'])
            if res.returncode == 0:
                return
        except Exception:
            pass

    # 2. 次選同目錄的 啟動播放器.exe (已內嵌完整環境)
    if os.path.exists(exe_cand):
        try:
            res = subprocess.run([exe_cand, '--transcode'])
            if res.returncode == 0:
                return
        except Exception as e:
            print(f"[!] 呼叫 {exe_cand} 失敗: {e}")

    # 3. 備援嘗試直接 import server
    try:
        if BASE_DIR not in sys.path:
            sys.path.insert(0, BASE_DIR)
        import server
        server.batch_transcode_all()
    except Exception as e:
        print(f"[!] 批次轉碼啟動失敗: {e}\n[提示] 請確認目錄下包含 啟動播放器.exe 或 server.py！")

def main():
    print("=" * 65)
    print("✨ 《れじぇくろ！》輕量版 - 一鍵全量資源回補與離線快取轉碼工具")
    print(f"👉 目標 CDN: {CDN_BASE}")
    print(f"📁 本地資源儲存路徑: {RESOURCE_DIR}")
    print("=" * 65)

    manifest_path = os.path.join(BASE_DIR, 'cdn_manifest.json')
    model_map_path = os.path.join(BASE_DIR, 'char_model_map.json')

    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

    model_map = {}
    if os.path.exists(model_map_path):
        with open(model_map_path, 'r', encoding='utf-8') as f:
            model_map = json.load(f)

    # 分類建立工作任務
    tasks_scenario = []
    tasks_standing = []
    tasks_voice = []
    tasks_still = []
    tasks_movie = []

    # 1. 立繪
    for cid, m_info in model_map.items():
        folder = m_info.get('folder', '')
        pfx = m_info.get('prefix', '')
        if not folder or not pfx:
            continue
        exp_dir = os.path.join(RESOURCE_DIR, 'characters', folder, 'avatar', 'standing', 'export')
        for ext in ['.atlas.txt', '.skel.bytes', '_material.mat']:
            tasks_standing.append((
                f"characters/{folder}/avatar/standing/export/{pfx}{ext}",
                os.path.join(exp_dir, f"{pfx}{ext}")
            ))

    # 2. 劇本、動畫、插圖、語音
    for cid, eps in manifest.items():
        for ep, data in eps.items():
            sc = data.get('scenario')
            if sc:
                tasks_scenario.append((f"adv/scenario/{sc}", os.path.join(RESOURCE_DIR, 'adv', 'scenario', sc)))
            vc = data.get('voice')
            if vc:
                tasks_voice.append((f"sound/webgl/adv/{vc}", os.path.join(RESOURCE_DIR, 'sound', 'adv', vc)))
            for st in data.get('stills', []):
                tasks_still.append((f"adv/still/{st}", os.path.join(RESOURCE_DIR, 'adv', 'still', st)))
            for mo in data.get('movies', []):
                tasks_movie.append((f"adv/movie/{mo}", os.path.join(RESOURCE_DIR, 'adv', 'movie', mo)))

    print("請選擇您希望回補的資源類型：")
    print("  [1] 極速回補：全角色立繪骨骼 + 劇本腳本 (約 120MB，全角色立繪對白離線可用)")
    print("  [2] 標準回補：選項 1 + 全角色語音音訊 (約 3.5GB，離線享有全角色語音)")
    print("  [3] 完整回補：選項 2 + 全角色插圖 CG (約 4.0GB)")
    print("  [4] 全量下載：所有立繪 + 劇本 + 語音 + 插圖 + 全部動畫電影 (約 9~11GB)")
    print("  [5] 旗艦全量：全量下載 [4] + 自動批次轉碼 (一鍵打造完全離線快取，可直傳手機)")
    print("  [6] 僅批次轉碼：將本機已下載的 resources/ 轉成 cache/ (生成手機與完全離線快取)")
    print("  [0] 退出")
    print()

    choice = safe_input("請輸入選項代號 [1-6] (預設 1): ", "1")

    if choice == "0":
        return

    if choice == "6":
        run_transcode()
        safe_input("\n按 Enter 鍵結束...")
        return

    active_tasks = []
    if choice == "1":
        active_tasks = tasks_standing + tasks_scenario
    elif choice == "2":
        active_tasks = tasks_standing + tasks_scenario + tasks_voice
    elif choice == "3":
        active_tasks = tasks_standing + tasks_scenario + tasks_voice + tasks_still
    elif choice in ("4", "5"):
        active_tasks = tasks_standing + tasks_scenario + tasks_voice + tasks_still + tasks_movie
    else:
        print("[提示] 無效的選項，將以選項 1 執行。")
        active_tasks = tasks_standing + tasks_scenario

    # 去重
    unique_tasks = list({rel: loc for rel, loc in active_tasks}.items())
    total = len(unique_tasks)

    # 檢查已存在
    already_done = sum(1 for rel, loc in unique_tasks if os.path.exists(loc) and os.path.getsize(loc) > 0)
    to_download = total - already_done

    print(f"\n[*] 總計檔案數: {total} 個 | 本機已存在: {already_done} 個 | 待下載: {to_download} 個")
    if to_download == 0:
        print("🎉 所有選定資源已全部存在於本機，無需再次下載！")
    else:
        print("[*] 正在啟動 8 線程平行下載中... (可隨時按 Ctrl+C 中斷，下次可接續下載)")
        start_time = time.time()
        completed = 0
        success = 0
        failed = 0

        errors = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_map = {executor.submit(fetch_file, rel, loc): rel for rel, loc in unique_tasks}
            for future in as_completed(future_map):
                completed += 1
                rel = future_map[future]
                try:
                    ok, status = future.result()
                    if ok:
                        success += 1
                    else:
                        failed += 1
                        errors.append((rel, status))
                except Exception as e:
                    failed += 1
                    errors.append((rel, str(e)))

                if completed % 10 == 0 or completed == total:
                    pct = (completed / total) * 100
                    elapsed = time.time() - start_time
                    speed = completed / elapsed if elapsed > 0 else 0
                    print(f"\r[*] 進度: {completed}/{total} ({pct:.1f}%) | 成功: {success} | 略過/失敗: {failed} | {speed:.1f} 個/秒", end="", flush=True)

        print()
        print("=" * 65)
        print(f"🎉 資源下載作業完成！共處理 {completed} 個檔案，總耗時: {time.time()-start_time:.1f} 秒")
        if errors:
            log_path = os.path.join(BASE_DIR, 'download_errors.log')
            try:
                with open(log_path, 'w', encoding='utf-8') as f:
                    for rel, status in errors:
                        f.write(f"{rel}\t{status}\n")
                print(f"[!] 注意：有 {len(errors)} 個檔案下載失敗，詳細錯誤清單已儲存至：{log_path}")
            except Exception:
                pass
        print("=" * 65)

    # 執行轉碼
    if choice == "5":
        run_transcode()
    else:
        ans = safe_input("\n是否立即對下載的素材執行批次轉碼 (生成手機與離線快取)？ [Y/n] (預設 Y): ", "y").lower()
        if ans != 'n':
            run_transcode()

    safe_input("\n按 Enter 鍵結束...")

if __name__ == '__main__':
    main()
