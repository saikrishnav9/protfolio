from pulse.config import ROOT
from pulse.site_build import assemble_site


def test_assemble_site_puts_pulse_under_portfolio():
    root = assemble_site()
    assert (root / "index.html").exists()
    assert (root / "pulse" / "index.html").exists()
    assert (root / "Sai_Krishna_Vasireddy_Resume.pdf").exists()
    profile = (ROOT / "site" / "profile.js").read_text(encoding="utf-8")
    assert "Vasireddy" in profile
    assert "Xiphoid" in profile
    assert "561-299-0093" in profile
    assert "Iron Mountain" not in profile
    assert "LangChain" in profile
    assert (ROOT / "site" / "projects.js").read_text(encoding="utf-8").find("pulse") >= 0
