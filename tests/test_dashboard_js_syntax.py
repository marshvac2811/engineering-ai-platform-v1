"""Every inline <script> in the dashboard must be syntactically valid JavaScript;
one syntax error leaves Jobs and the Report Register stuck on 'Loading...'."""
import pathlib, re, shutil, subprocess, tempfile
import pytest

HTML = pathlib.Path(__file__).resolve().parents[1] / "web" / "app.html"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_dashboard_inline_scripts_parse():
    scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", HTML.read_text(encoding="utf-8"), re.S)
    assert scripts
    for i, code in enumerate(scripts):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(code)
        r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
        assert r.returncode == 0, f"script {i}: {r.stderr[:500]}"
