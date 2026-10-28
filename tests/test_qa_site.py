"""Navigation and statistical contracts of the compact QA site."""

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("qa_viewer", SCRIPTS / "explore_viewer.py")
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)
from species_compare import shift_row


def test_decisions_link_to_guide_without_duplicate_report_or_banner():
    tx = {"taxon_id": "example", "english_name": "Example"}
    q = {c: {"class": "show", "reasons": []} for c in viewer.CLAIMS}
    q.update(elements={"season.phenology": "hide"}, inputs={"gap_error": 0.1})
    body = viewer.taxon_details(tx, {"reliability": q})
    assert "<summary>Example</summary>" in body
    assert "index.html?species=example#reliability" in body
    assert 'class="badge hide"' in body
    page = viewer.wrap("QA", body, {"built_at": "SECRET_BANNER"})
    assert "SECRET_BANNER" not in page
    assert "t.tHead.querySelectorAll" in viewer.INDEX_JS


def test_comparison_uses_annual_date_regression_and_joint_interval():
    fit = {
        "year": [2000, 2020],
        "date": [250, 254],
        "slope": 0.2,
        "slope_lo": 0.1,
        "slope_hi": 0.3,
    }
    sp = {
        "season": {"phenology": {"quantiles": {"q10": fit, "q50": fit, "q90": fit}}},
        "reliability": None,
    }
    row = shift_row(sp)
    assert row["q50"] == {"d": 4, "lo": 2, "hi": 6, "from": 250, "to": 254}
