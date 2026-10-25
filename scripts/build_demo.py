"""Write the self-contained replay page to dist/replay.html (and an artifact fragment)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.static_build import build_static_html  # noqa: E402

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 21
out = ROOT / "dist"
out.mkdir(exist_ok=True)
(out / "replay.html").write_text(build_static_html(seed), encoding="utf-8")
(out / "replay.fragment.html").write_text(build_static_html(seed, fragment=True), encoding="utf-8")
print(f"wrote {out / 'replay.html'}")
