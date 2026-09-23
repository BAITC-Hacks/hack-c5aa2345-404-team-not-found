"""Superseded webview packaging experiment; active client is desktop/native/."""
from __future__ import annotations

import argparse
import atexit
import ctypes
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def data_directory() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    target = base / "SAMRUK_KAZYNA"
    target.mkdir(parents=True, exist_ok=True)
    return target


def prepare_logging() -> None:
    handler = RotatingFileHandler(data_directory() / "launcher.log", maxBytes=1_000_000,
                                  backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format="%(asctime)s %(levelname)s %(message)s")
    # PyInstaller's windowed bootloader sets these to None. Streamlit/Click need
    # real streams, including in the child which inherits redirected OS handles.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(data_directory() / "runtime.log", "a", encoding="utf-8", buffering=1)


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def watch_parent(parent_pid: int) -> None:
    """Avoid orphaned UI servers even if the window process is terminated."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x00100000, False, parent_pid)  # SYNCHRONIZE only
    if not handle:
        os._exit(0)
    try:
        kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
    finally:
        kernel.CloseHandle(handle)
    os._exit(0)


def serve(port: int, parent_pid: int) -> None:
    if not 1 <= port <= 65535 or parent_pid <= 0:
        raise ValueError("Invalid internal server arguments")
    threading.Thread(target=watch_parent, args=(parent_pid,), daemon=True).start()
    root = resource_root()
    sys.path.insert(0, str(root))
    # The CWD is writable app data, never the installation or repository folder.
    os.chdir(data_directory())
    from streamlit.web import bootstrap

    options = {
        "global.developmentMode": False,
        "server.address": "127.0.0.1",
        "server.port": port,
        "server.headless": True,
        "server.fileWatcherType": "none",
        "server.runOnSave": False,
        "server.maxUploadSize": 500,
        "server.enableCORS": True,
        "server.enableXsrfProtection": True,
        "browser.gatherUsageStats": False,
        "browser.serverAddress": "127.0.0.1",
        "client.toolbarMode": "minimal",
        "theme.base": "light",
        "theme.primaryColor": "#137f76",
        "theme.backgroundColor": "#f4f7f9",
        "theme.secondaryBackgroundColor": "#ffffff",
        "theme.textColor": "#1d2b3a",
    }
    bootstrap.load_config_options(options)
    bootstrap.run(str(root / "frontend" / "app.py"), False, [], options)


def wait_for_server(process: subprocess.Popen, port: int, timeout: float = 60) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"UI server exited ({process.returncode})")
        try:
            with opener.open(f"http://127.0.0.1:{port}/_stcore/health", timeout=1) as response:
                if response.status == 200 and response.read().strip() == b"ok":
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.2)
    raise TimeoutError("The local UI server did not start within 60 seconds")


def stop_server(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def run_window() -> None:
    os.environ["QT_API"] = "pyside6"
    # PyInstaller's Qt hook supplies the bundled plugin path.
    os.environ.pop("QTWEBENGINE_REMOTE_DEBUGGING", None)
    command = [sys.executable]
    if not getattr(sys, "frozen", False):
        command.append(str(Path(__file__).resolve()))

    process = None
    port = 0
    with open(data_directory() / "server.log", "w", encoding="utf-8") as server_log:
        # A just-released ephemeral port can be taken by another process.
        for attempt in range(3):
            port = available_port()
            process = subprocess.Popen(
                [*command, "--serve", str(port), "--parent-pid", str(os.getpid())],
                cwd=data_directory(), stdin=subprocess.DEVNULL,
                stdout=server_log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            try:
                wait_for_server(process, port)
                break
            except Exception:
                stop_server(process)
                if attempt == 2:
                    raise
        assert process is not None
        atexit.register(stop_server, process)
        logging.info("Desktop ready: UI http://127.0.0.1:%d, server pid %d", port, process.pid)
        try:
            # Preserve the original DLL/import error instead of QtPy's generic
            # "No Qt bindings" message if a portable runtime is incomplete.
            from PySide6 import QtCore
            logging.info("Bundled Qt %s", QtCore.__version__)
            import webview

            webview.settings["ALLOW_DOWNLOADS"] = True
            window = webview.create_window(
                "SAMRUK KAZYNA", f"http://127.0.0.1:{port}",
                width=1320, height=880, min_size=(900, 640),
                background_color="#f4f7f9",
            )
            closing = threading.Event()
            window.events.closed += closing.set

            def monitor_server() -> None:
                exit_code = process.wait()
                if not closing.is_set():
                    logging.error("UI server exited while the desktop was open (%d)", exit_code)
                    window.destroy()

            # No JS API is exposed to the page. Qt includes Chromium resources
            # in the portable directory; no runtime download is necessary.
            webview.start(monitor_server, gui="qt", debug=False, private_mode=True)
        finally:
            if "closing" in locals():
                closing.set()
            stop_server(process)
            atexit.unregister(stop_server)
            logging.info("Desktop stopped; owned UI process terminated")


def main() -> int:
    prepare_logging()
    parser = argparse.ArgumentParser(description="SAMRUK KAZYNA Windows client")
    parser.add_argument("--serve", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--parent-pid", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.serve is not None:
            serve(args.serve, args.parent_pid)
        else:
            run_window()
        return 0
    except Exception:
        logging.exception("Application startup failed")
        if args.serve is None:
            ctypes.windll.user32.MessageBoxW(
                None,
                "Не удалось запустить SAMRUK KAZYNA.\n"
                "Распакуйте весь архив вместе с папкой _internal.\n\n"
                f"Журнал ошибки: {data_directory() / 'launcher.log'}",
                "SAMRUK KAZYNA", 0x10,
            )
        return 1


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(main())
