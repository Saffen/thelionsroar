import argparse
import json
import mimetypes
import socket
import sys
import threading
import urllib.parse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def find_internal_build_root(html_path: Path) -> Path:
    for parent in [html_path.parent, *html_path.parents]:
        if parent.name == "internal" and parent.parent.name == "build":
            return parent
    raise ValueError(f"{html_path} is not inside build/internal")


class QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return


def start_static_server(root: Path) -> tuple[ThreadingHTTPServer, int]:
    port = find_free_port()
    handler = partial(QuietStaticHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def local_asset_for_url(build_root: Path, url: str) -> Path | None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.path.startswith("/assets/"):
        candidate = (build_root / parsed.path.lstrip("/")).resolve()
        try:
            candidate.relative_to(build_root.resolve())
        except ValueError:
            return None
        if candidate.is_file():
            return candidate
    return None


def export_pdf(html_path: Path, output_path: Path, viewport_width: int, timeout_ms: int, theme: str) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required for PDF export. Install it with "
            "'python -m pip install playwright' and then run "
            "'python -m playwright install chromium'."
        ) from exc

    html_path = html_path.resolve()
    if not html_path.is_file():
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    build_root = find_internal_build_root(html_path)
    relative_url = html_path.relative_to(build_root).as_posix()
    if relative_url.endswith("/index.html"):
        relative_url = relative_url[: -len("index.html")]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    server, port = start_static_server(build_root)
    local_url = f"http://127.0.0.1:{port}/{relative_url}"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": viewport_width, "height": 900})
                theme_script = (
                    "(() => {"
                    f"const theme = {json.dumps(theme)};"
                    "localStorage.setItem('lr-theme', theme);"
                    "document.documentElement.setAttribute('data-theme', theme);"
                    "})();"
                )
                page.add_init_script(theme_script)

                def route_assets(route) -> None:
                    asset_path = local_asset_for_url(build_root, route.request.url)
                    if not asset_path:
                        route.continue_()
                        return

                    mime_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
                    route.fulfill(path=str(asset_path), content_type=mime_type)

                page.route("https://thelionsroar.eu/assets/**", route_assets)
                page.route("http://thelionsroar.eu/assets/**", route_assets)
                page.emulate_media(media="screen")
                page.goto(local_url, wait_until="networkidle", timeout=timeout_ms)
                page.evaluate(
                    """theme => {
                        localStorage.setItem('lr-theme', theme);
                        document.documentElement.setAttribute('data-theme', theme);
                    }""",
                    theme,
                )

                dimensions = page.evaluate(
                    """() => {
                        const body = document.body;
                        const html = document.documentElement;
                        return {
                            width: Math.max(body.scrollWidth, html.scrollWidth, document.documentElement.clientWidth),
                            height: Math.max(body.scrollHeight, html.scrollHeight, document.documentElement.clientHeight)
                        };
                    }"""
                )
                pdf_width = max(int(dimensions["width"]), viewport_width)
                pdf_height = max(int(dimensions["height"]), 900)
                page.pdf(
                    path=str(output_path),
                    width=f"{pdf_width}px",
                    height=f"{pdf_height}px",
                    print_background=True,
                    margin={"top": "0px", "right": "0px", "bottom": "0px", "left": "0px"},
                )
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a built internal article HTML page to a one-page PDF.")
    parser.add_argument("html_path", help="Path to a built HTML file inside build/internal")
    parser.add_argument("--out", required=True, help="PDF output path")
    parser.add_argument("--theme", choices=["light", "dark", "immersive"], default="immersive", help="Theme to apply before exporting")
    parser.add_argument("--viewport-width", type=int, default=1440, help="Browser viewport width in CSS pixels")
    parser.add_argument("--timeout-ms", type=int, default=60000, help="Page load timeout in milliseconds")
    args = parser.parse_args()

    try:
        export_pdf(
            Path(args.html_path),
            Path(args.out),
            viewport_width=max(320, args.viewport_width),
            timeout_ms=max(1000, args.timeout_ms),
            theme=args.theme,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(Path(args.out).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
