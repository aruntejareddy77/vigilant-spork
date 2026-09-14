"""
tests/test_server/test_static_assets.py
Static asset air-gap audit test validating zero external CDN/script/font references,
inline SVG completeness, and FastAPI static file mounting.
"""
import re
from pathlib import Path
from fastapi.testclient import TestClient

from sovereign.server.app import create_app
from sovereign.server.config import ServerConfig

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "sovereign" / "server" / "static"


class TestStaticAssetsAirGap:
    """Validate 100% self-contained air-gap asset posture (zero external CDNs)."""

    def test_static_directory_and_files_exist(self):
        """Ensure all required core static files are present."""
        assert STATIC_DIR.exists(), f"Static directory does not exist: {STATIC_DIR}"
        expected_files = ["index.html", "styles.css", "app.js", "preview.js"]
        for fname in expected_files:
            file_path = STATIC_DIR / fname
            assert file_path.exists(), f"Expected static asset missing: {fname}"
            assert file_path.stat().st_size > 0, f"Static asset is empty: {fname}"

    def test_zero_external_network_urls_in_assets(self):
        """
        Verify that no static file references external URLs (http://, https://, //).
        This guarantees zero egress attempts upon page render in an air-gapped enclave.
        """
        external_url_patterns = [
            re.compile(r"https?://", re.IGNORECASE),
            re.compile(r"//[a-zA-Z0-9_\.-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
            re.compile(r"fonts\.googleapis\.com", re.IGNORECASE),
            re.compile(r"cdnjs\.cloudflare\.com", re.IGNORECASE),
            re.compile(r"unpkg\.com", re.IGNORECASE),
            re.compile(r"@import\s+url\(", re.IGNORECASE),
            re.compile(r"font-awesome", re.IGNORECASE),
        ]

        static_files = list(STATIC_DIR.glob("**/*"))
        assert len(static_files) >= 4, "Expected at least 4 static files"

        violations = []
        for sfile in static_files:
            if sfile.is_dir():
                continue
            content = sfile.read_text(encoding="utf-8")
            for pattern in external_url_patterns:
                matches = pattern.findall(content)
                if matches:
                    violations.append(f"{sfile.name}: found pattern {pattern.pattern} ({len(matches)} matches)")

        assert not violations, f"Air-gap audit failed! External dependencies found:\n" + "\n".join(violations)

    def test_svg_symbol_definitions_complete(self):
        """
        Verify that all <use href="#..."> references in index.html match defined <symbol id="...">.
        Also check for required icons: play, check, shield, terminal, document, eye, alert-triangle, lock, refresh.
        """
        index_file = STATIC_DIR / "index.html"
        content = index_file.read_text(encoding="utf-8")

        # Find all defined symbols
        defined_symbols = set(re.findall(r'<symbol\s+id="([^"]+)"', content))

        # Required symbols
        required_symbols = {
            "icon-play",
            "icon-check",
            "icon-shield",
            "icon-terminal",
            "icon-document",
            "icon-eye",
            "icon-alert-triangle",
            "icon-lock",
            "icon-refresh",
        }
        for req in required_symbols:
            assert req in defined_symbols, f"Required SVG symbol '{req}' missing from index.html"

        # Find all references
        referenced_symbols = set(re.findall(r'<use\s+href="#([^"]+)"', content))
        for ref in referenced_symbols:
            assert ref in defined_symbols, f"Referenced SVG symbol '#{ref}' not defined in index.html"

    def test_index_html_required_dom_elements(self):
        """Validate presence of key multi-pane IDs and controls in index.html."""
        index_file = STATIC_DIR / "index.html"
        content = index_file.read_text(encoding="utf-8")

        required_ids = [
            "role-selector",
            "egress-badge",
            "vram-pill",
            "btn-demo-a",
            "btn-demo-b",
            "btn-demo-c",
            "task-submission-container",
            "task-prompt",
            "task-file",
            "btn-submit-task",
            "auditor-notice",
            "pane-trace",
            "trace-timeline",
            "pane-preview",
            "preview-canvas",
            "pane-hitl",
            "hitl-queue-container",
            "pane-network",
            "network-counters",
            "network-events-table",
            "btn-run-egress-check",
        ]
        for elem_id in required_ids:
            assert f'id="{elem_id}"' in content, f"Required DOM element id='{elem_id}' missing in index.html"


class TestStaticMountEndpoints:
    """Test serving of static assets via FastAPI TestClient."""

    def test_root_serves_index_html(self):
        """GET / returns index.html with 200 OK and text/html."""
        app = create_app()
        client = TestClient(app, base_url="http://localhost:8000")
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "SOVEREIGN AI WORKBENCH" in response.text
        assert "pane-trace" in response.text

    def test_static_css_served(self):
        """GET /static/styles.css returns CSS with 200 OK."""
        app = create_app()
        client = TestClient(app, base_url="http://localhost:8000")
        response = client.get("/static/styles.css")
        assert response.status_code == 200
        assert "text/css" in response.headers.get("content-type", "")
        assert "--bg-primary" in response.text

    def test_static_js_served(self):
        """GET /static/app.js and preview.js return JavaScript with 200 OK."""
        app = create_app()
        client = TestClient(app, base_url="http://localhost:8000")

        res_app = client.get("/static/app.js")
        assert res_app.status_code == 200
        assert "javascript" in res_app.headers.get("content-type", "")
        assert "appState" in res_app.text

        res_prev = client.get("/static/preview.js")
        assert res_prev.status_code == 200
        assert "javascript" in res_prev.headers.get("content-type", "")
        assert "DocumentPreviewRenderer" in res_prev.text
