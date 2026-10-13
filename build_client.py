"""
QIntellect AI Attendance System - Fast Client Distribution Builder
- Produces a 100% standalone, closed-binary executable package (.exe) for the client.
- No source code (.py) is exposed; all code is compiled into binary bytecode.
- Includes the selected client database and its employee/attendance records.
- Optimized for speed: uses incremental PyInstaller caching for sub-2-minute updates.
"""

import os
import sys
import time
import subprocess
import shutil
import sqlite3
from pathlib import Path


def snapshot_client_database(source_db, destination_db):
    """Create a consistent SQLite snapshot without changing the source database."""
    source_db = Path(source_db).resolve()
    destination_db = Path(destination_db)
    if not source_db.is_file():
        raise FileNotFoundError(f"Client source database not found: {source_db}")

    source_uri = f"file:{source_db.as_posix()}?mode=ro"
    source_connection = sqlite3.connect(source_uri, uri=True, timeout=30)
    try:
        tables = {row[0] for row in source_connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"users", "attendance", "embeddings"}.issubset(tables):
            raise RuntimeError(f"Client source database has an incomplete schema: {source_db}")
        user_count = source_connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            raise RuntimeError(f"Client source database contains no employees: {source_db}")

        destination_db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(destination_db), timeout=30) as destination_connection:
            source_connection.backup(destination_connection)
    finally:
        source_connection.close()

    with sqlite3.connect(str(destination_db)) as verify_connection:
        copied_count = verify_connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if copied_count != user_count:
        raise RuntimeError(f"Database snapshot verification failed: expected {user_count} employees, found {copied_count}")
    return user_count


def build_client():
    start_time = time.time()
    print("=" * 65)
    print("   QINTELLECT AI ATTENDANCE SYSTEM - FAST CLIENT BUILDER")
    print("=" * 65)

    base_dir = Path(__file__).parent.resolve()

    # Step 0: Terminate any running instances to release Windows file locks
    if os.name == 'nt':
        subprocess.run(
            ["taskkill", "/F", "/IM", "QIntellect_Attendance.exe"],
            stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL
        )

    # Use pilot_env virtual environment python if available
    build_python = base_dir / "pilot_env" / "Scripts" / "python.exe"
    if not build_python.is_file():
        build_python = Path(sys.executable)
    print(f"[*] Build Python runtime : {build_python}")

    # Step 1: Use short path on Windows to avoid MAX_PATH (260-char) limit
    short_root = Path(r"C:\QIntellect_Build") if os.name == 'nt' else base_dir / "build_temp"
    short_dist = short_root / f"dist_{os.getpid()}"
    short_work = short_root / "work"
    short_root.mkdir(parents=True, exist_ok=True)
    short_dist.mkdir(parents=True, exist_ok=True)
    short_work.mkdir(parents=True, exist_ok=True)

    output_dir = short_dist / "QIntellect_Attendance"
    final_dist = base_dir / "dist" / "QIntellect_Attendance"
    final_zip = base_dir / "dist" / "QIntellect_Attendance_Client.zip"

    # Step 2: Ensure PyInstaller is installed in the build environment
    try:
        subprocess.check_call(
            [str(build_python), "-m", "PyInstaller", "--version"],
            cwd=base_dir,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        print("[*] Installing PyInstaller into build environment...")
        subprocess.check_call([str(build_python), "-m", "pip", "install", "pyinstaller"], cwd=base_dir)

    # Step 2.5: FRESHNESS GUARANTEE - stamp all project source files with the current time.
    # PyInstaller only re-analyses code whose modification time is newer than its cached
    # Analysis TOC. If a file was edited while a previous build was running, the cache would
    # silently keep the OLD code. Touching every source file forces the latest code in.
    now_ts = time.time()
    touched = 0
    for pattern in ("*.py",):
        for src in base_dir.glob(pattern):
            if src.name.startswith(("build_", "pilot_")):
                continue
            try:
                os.utime(src, (now_ts, now_ts))
                touched += 1
            except Exception:
                pass
    for folder in ("templates", "static"):
        for src in (base_dir / folder).rglob("*"):
            if src.is_file():
                try:
                    os.utime(src, (now_ts, now_ts))
                    touched += 1
                except Exception:
                    pass
    print(f"[*] Freshness check: stamped {touched} source files so the build uses the latest code")

    # Step 3: Compile the application. The selected client DB is added as a verified
    # SQLite snapshot after PyInstaller completes.
    print("\n[*] Compiling standalone application binary (PyInstaller)...")
    command = [
        str(build_python), "-m", "PyInstaller",
        "--name", "QIntellect_Attendance",
        "--onedir",
        "--noconsole",
        "--noconfirm",
        "--distpath", str(short_dist),
        "--workpath", str(short_work),
        "--add-data", f"templates{os.pathsep}templates",
        "--add-data", f"static{os.pathsep}static",
        "--add-data", f"yolov8n.pt{os.pathsep}.",
        "--add-data", f"models{os.pathsep}models",
        "--collect-data", "insightface",
        "app.py"
    ]

    print("    " + " ".join(command))
    compilation_start = time.time()
    subprocess.check_call(command, cwd=base_dir)
    print(f"[OK] Binary compilation finished in {time.time() - compilation_start:.1f}s")

    # Step 3.5: Purge any auto-collected DB before copying in the selected snapshot.
    for candidate_dir in [
        output_dir,
        output_dir / "_internal",
        short_dist / "QIntellect_Attendance" / "_internal",
    ]:
        if candidate_dir.exists():
            for db_file in candidate_dir.glob("*.db*"):
                try:
                    db_file.unlink()
                    print(f"[*] Removed bundled DB from build output: {db_file.name}")
                except Exception:
                    pass

    # Step 4: Fast sync to local dist/ folder (uses Windows native robocopy with 16 threads)
    print(f"\n[*] Syncing package to final distribution folder: {final_dist}")
    final_dist.mkdir(parents=True, exist_ok=True)
    sync_done = False
    if os.name == 'nt':
        try:
            rc = subprocess.run(
                ["robocopy", str(output_dir), str(final_dist), "/MIR", "/MT:16", "/NFL", "/NDL", "/NJH", "/NJS"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            # Robocopy exit codes 0-7 indicate success
            if rc.returncode < 8:
                sync_done = True
        except Exception as e:
            print(f"[!] Robocopy note: {e}")

    if not sync_done:
        if final_dist.exists():
            try:
                shutil.rmtree(final_dist)
            except Exception:
                pass
        shutil.copytree(str(output_dir), str(final_dist), dirs_exist_ok=True)

    # Step 5: Remove transient package data while retaining the selected client DB.
    print("\n[*] Cleaning transient package data while preserving the selected client database...")
    purged_count = 0
    for target in (output_dir, final_dist):
        if not target.exists():
            continue
        internal_dir = target / "_internal"
        # Remove any bundled employee photos
        for p_dir in [target / "static" / "profile_photos", target / "profile_photos",
                      internal_dir / "static" / "profile_photos"]:
            if p_dir.exists():
                for photo in p_dir.glob("*"):
                    if photo.is_file():
                        try:
                            photo.unlink()
                            purged_count += 1
                        except Exception:
                            pass
        # Remove any uploads or logs
        for u_dir in [target / "uploads", target / "logs"]:
            if u_dir.exists():
                for item in u_dir.glob("*"):
                    if item.is_file():
                        try:
                            item.unlink()
                            purged_count += 1
                        except Exception:
                            pass
    print(f"    Purged {purged_count} stale data file(s) from build output.")

    # Step 5b: Snapshot the selected source database into the client package.
    # SQLite backup includes committed WAL data and leaves the source untouched.
    print("\n[*] Including the existing client employee and attendance database...")
    source_db_path = base_dir / 'attendance.db'
    packaged_db_path = final_dist / 'attendance.db'
    try:
        employee_count = snapshot_client_database(source_db_path, packaged_db_path)
        print(f"    Included {employee_count} employees from {source_db_path.name} ({packaged_db_path.stat().st_size:,} bytes)")
    except Exception as e:
        print(f"[!] Client database snapshot failed: {e}")
        raise

    # Copy fresh client_config.json
    fresh_cfg = base_dir / "client_config.json"
    if fresh_cfg.exists():
        shutil.copy2(fresh_cfg, final_dist / "client_config.json")

    # Step 6: Create client-ready ZIP archive using fast multi-file streaming
    print(f"\n[*] Creating deployable ZIP archive: {final_zip}")
    (base_dir / "dist").mkdir(parents=True, exist_ok=True)
    if final_zip.exists():
        try:
            os.remove(final_zip)
        except Exception:
            pass

    import zipfile
    zip_start = time.time()
    with zipfile.ZipFile(str(final_zip), 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        root_path = base_dir / "dist"
        for foldername, subfolders, filenames in os.walk(str(final_dist)):
            for filename in filenames:
                filepath = Path(foldername) / filename
                arcname = filepath.relative_to(root_path)
                zf.write(filepath, arcname)
    print(f"[OK] ZIP creation completed in {time.time() - zip_start:.1f}s")
    zip_size_mb = final_zip.stat().st_size / (1024 * 1024) if final_zip.exists() else 0
    total_elapsed = time.time() - start_time

    print("\n" + "=" * 65)
    print("   [SUCCESS] CLIENT STANDALONE PACKAGE READY!")
    print("=" * 65)
    print(f"  Distribution Folder : {final_dist}")
    print(f"  Client Executable   : {final_dist / 'QIntellect_Attendance.exe'}")
    print(f"  Deployable ZIP      : {final_zip} ({zip_size_mb:.1f} MB)")
    print(f"  Total Build Time    : {total_elapsed:.1f} seconds")
    print("=" * 65)
    print("Client Instructions: Unzip and double-click 'QIntellect_Attendance.exe'")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    build_client()
