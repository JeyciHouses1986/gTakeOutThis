import argparse
import asyncio
from pathlib import Path
from rich.console import Console
from .downloader import download_all
from .extractor import extract_all
from .organizer import organize_photos

console = Console()


def _existing_dir(path_str: str) -> Path:
	p = Path(path_str)
	if not p.exists() or not p.is_dir():
		raise argparse.ArgumentTypeError(f"Directory does not exist: {p}")
	return p


def _ensure_dir(path_str: str) -> Path:
	p = Path(path_str)
	p.mkdir(parents=True, exist_ok=True)
	return p


def main() -> None:
	parser = argparse.ArgumentParser(prog="gtakeout", description="Google Takeout helper")
	sub = parser.add_subparsers(dest="cmd", required=True)

	p_dl = sub.add_parser("download", help="Open Takeout page and download all parts sequentially")
	p_dl.add_argument("--url", required=True, help="Takeout download page URL")
	p_dl.add_argument("--download-dir", required=True, type=_ensure_dir, help="Directory to save downloads")
	p_dl.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")

	p_ex = sub.add_parser("extract", help="Extract all ZIPs from download dir")
	p_ex.add_argument("--download-dir", required=True, type=_existing_dir)
	p_ex.add_argument("--extract-dir", required=True, type=_ensure_dir)

	p_org = sub.add_parser("organize", help="Organize photos by EXIF/JSON dates")
	p_org.add_argument("--source-dir", required=True, type=_existing_dir)
	p_org.add_argument("--dest-dir", required=True, type=_ensure_dir)

	args = parser.parse_args()

	if args.cmd == "download":
		asyncio.run(download_all(args.url, args.download_dir, args.browser))
	elif args.cmd == "extract":
		extract_all(args.download_dir, args.extract_dir)
	elif args.cmd == "organize":
		organize_photos(args.source_dir, args.dest_dir)
	else:
		raise SystemExit(1)


if __name__ == "__main__":
	main()
