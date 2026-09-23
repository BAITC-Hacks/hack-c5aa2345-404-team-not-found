"""Interactive, hidden token entry. Never pass a token on the command line."""
import getpass
import os
import warnings
from pathlib import Path

root = Path(os.environ.get("HACKALEM_AI_HOME", str(Path(os.environ["LOCALAPPDATA"]) / "HackAlemAI")))
os.environ["HF_HOME"] = str(root / "huggingface")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["DO_NOT_TRACK"] = "1"

from huggingface_hub import HfApi, login

warnings.simplefilter("error", getpass.GetPassWarning)
try:
    token = getpass.getpass("Hugging Face read token (hidden; paste and press Enter): ").strip()
except getpass.GetPassWarning:
    raise SystemExit("Hidden entry is unavailable. Run this script in your own interactive terminal.")
try:
    HfApi().whoami(token=token)
    login(token=token, add_to_git_credential=False)
    print("Saved outside Git. You can return to the task.")
except Exception as exc:
    print(f"Login failed ({type(exc).__name__}). Check the token and access permissions.")
    raise SystemExit(1)
finally:
    token = None
