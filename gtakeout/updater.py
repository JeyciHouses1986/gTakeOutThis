from __future__ import annotations

import webbrowser
from typing import Optional, Tuple
import requests


def get_latest_release(owner: str, repo: str, timeout: float = 5.0) -> Optional[str]:
	try:
		resp = requests.get(f"https://api.github.com/repos/{owner}/{repo}/releases/latest", timeout=timeout)
		if resp.ok:
			return str(resp.json().get("tag_name") or "").strip() or None
	except Exception:
		return None
	return None


def open_releases_page(owner: str, repo: str) -> None:
	webbrowser.open(f"https://github.com/{owner}/{repo}/releases")
