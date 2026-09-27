import os
import sys
import subprocess
import time
from pathlib import Path

# Fix Windows console UTF-8 output
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def find_adb():
    candidates = [
        Path("../platform-tools/adb.exe"),
        Path("../adb.exe"),
        Path("adb.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
    ]
    for c in candidates:
        if c.exists():
            return str(c.resolve())
    # Try system PATH
    try:
        res = subprocess.run(["adb", "version"], capture_output=True, text=True)
        if res.returncode == 0:
            return "adb"
    except Exception:
        pass
    return None

def get_connected_device(adb):
    try:
        res = subprocess.run([adb, "devices"], capture_output=True, text=True)
        lines = res.stdout.strip().splitlines()[1:]
        devices = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
    except Exception as e:
        print(f"[-] 無法執行 ADB: {e}")
        return []

def main():
    print("=" * 60)
    print("📱 LegecloPlayer 手機離線資源同步工具 (PC -> Android)")
    print("=" * 60)

    adb = find_adb()
    if not adb:
        print("❌ 找不到 adb.exe！請確認手機已透過 USB 傳輸線連接且已安裝驅動。")
        input("\n按 Enter 鍵關閉...")
        return 1

    devices = get_connected_device(adb)
    if not devices:
        print("❌ 未檢測到已連接且授權的 Android 手機！")
        print("👉 請確認：")
        print("   1. 手機已插上 USB 傳輸線")
        print("   2. 手機已開啟「開發人員選項」及「USB 偵錯」")
        print("   3. 手機螢幕若彈出「允許這台電腦進行 USB 偵錯？」，請勾選一律允許並按「確定」")
        input("\n按 Enter 鍵關閉...")
        return 1

    device_id = devices[0]
    print(f"[+] 已連線設備: {device_id} (共 {len(devices)} 台設備)")

    # Source cache folder candidates
    cache_candidates = [
        Path(r"D:\LegecloPlayer_Lite\LegecloPlayer_Lite\cache"),
        Path(r"D:\LegecloPlayer_Lite\cache"),
        Path("../LegecloPlayer_Lite/cache"),
        Path("./cache")
    ]
    pc_cache = None
    for cand in cache_candidates:
        if cand.exists() and any(cand.iterdir()):
            pc_cache = cand
            break

    if not pc_cache:
        print("❌ 找不到電腦端的 cache 資料夾！請確認 LegecloPlayer_Lite/cache 存在。")
        input("\n按 Enter 鍵關閉...")
        return 1

    phone_cache = "/sdcard/Download/LegecloPlayer/cache"
    # Ensure remote directory exists
    subprocess.run([adb, "-s", device_id, "shell", f"mkdir -p {phone_cache}"], capture_output=True)

    # Inspect source folders
    subdirs = [d for d in pc_cache.iterdir() if d.is_dir()]
    chapter_dirs = [d for d in subdirs if d.name not in ('avatars', 'bgm', 'standing')]
    
    print(f"\n📂 電腦端檢測到快取項目:")
    print(f"   - 角色劇情章節: {len(chapter_dirs)} 個")
    print(f"   - 系統通用資料夾: avatars, bgm, standing")
    print(f"   - 手機目標路徑: {phone_cache}\n")

    print("請選擇同步方式:")
    print("  [1] 一鍵同步全部快取 (全章節 + 立繪 + 背景音效 + 大頭貼)")
    print("  [2] 僅同步系統底圖/立繪/大頭貼 (avatars + standing + bgm)")
    print("  [3] 僅同步特定章節資料夾")
    print("  [Q] 退出")

    choice = input("\n請輸入選項 (預設 1): ").strip()
    if choice.upper() == 'Q':
        print("已取消操作。")
        return 0

    if choice == '2':
        targets = [d for d in subdirs if d.name in ('avatars', 'bgm', 'standing')]
    elif choice == '3':
        print("\n可用的章節:")
        for idx, d in enumerate(chapter_dirs, 1):
            print(f"  {idx:2d}. {d.name}")
        sel = input("\n請輸入要同步的章節編號 (如 1,3 或直接輸入資料夾名稱): ").strip()
        targets = []
        if sel:
            for s in sel.split(','):
                s = s.strip()
                if s.isdigit() and 1 <= int(s) <= len(chapter_dirs):
                    targets.append(chapter_dirs[int(s) - 1])
                else:
                    matched = [d for d in chapter_dirs if s.lower() in d.name.lower()]
                    targets.extend(matched)
        targets = list(set(targets))
    else:
        # Default: All
        targets = subdirs

    if not targets:
        print("⚠️ 未選取任何資料夾，同步結束。")
        return 0

    print(f"\n🚀 開始推送 {len(targets)} 個資料夾至手機...")
    start_time = time.time()
    success_count = 0
    fail_count = 0

    for idx, folder in enumerate(targets, 1):
        print(f"[{idx}/{len(targets)}] 正在推送 {folder.name} ...", end="", flush=True)
        t0 = time.time()
        res = subprocess.run([adb, "-s", device_id, "push", str(folder), phone_cache], capture_output=True, text=True)
        elapsed = time.time() - t0
        if res.returncode == 0:
            print(f" ✔ 完成 ({elapsed:.1f}s)")
            success_count += 1
        else:
            print(f" ❌ 失敗: {res.stderr.strip()[:100]}")
            fail_count += 1

    total_time = time.time() - start_time
    print("=" * 60)
    print(f"🎉 同步完成！耗時: {total_time:.1f} 秒 | 成功: {success_count} 個，失敗: {fail_count} 個")
    print(f"📱 資源已儲存於手機: {phone_cache}/")
    print("💡 現在打開手機上的《LegecloPlayer》App 即可直接離線暢玩！")
    print("=" * 60)

    input("\n按 Enter 鍵關閉...")
    return 0

if __name__ == '__main__':
    sys.exit(main())
