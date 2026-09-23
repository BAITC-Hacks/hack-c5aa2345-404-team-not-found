# Superseded packaging experiment: desktop/build-webview-experiment.ps1.
# Active client is desktop/native/ and does not use this file.
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

os.environ["QT_API"] = "pyside6"
root = Path(SPECPATH).parent
datas = collect_data_files("streamlit") + copy_metadata("streamlit")
datas += [(str(path), str(path.parent.relative_to(root)))
          for path in (root / "frontend").rglob("*.py")]
datas += [(str(root / "desktop" / "PORTABLE-README.txt"), ".")]
hiddenimports = collect_submodules("frontend") + [
    "streamlit.web.bootstrap", "webview.platforms.qt", "qtpy",
    "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore", "PySide6.QtWebChannel",
    "docx", "reportlab.platypus", "reportlab.pdfbase.ttfonts",
]

a = Analysis(
    [str(root / "desktop" / "launcher.py")], pathex=[str(root)],
    binaries=[], datas=datas, hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "tkinter", "matplotlib", "scipy",
              "torch", "tensorflow", "streamlit.external.langchain",
              "webview.platforms.winforms", "webview.platforms.edgechromium",
              "webview.platforms.cef", "webview.platforms.gtk", "webview.platforms.cocoa",
              "webview.platforms.android", "clr", "pythonnet"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SAMRUK-KAZYNA",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="SAMRUK-KAZYNA")
