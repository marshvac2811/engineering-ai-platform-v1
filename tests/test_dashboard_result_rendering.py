from pathlib import Path
import re


def test_dashboard_uses_distinct_labels_for_pump_head_pressure_conversions():
    html = (Path(__file__).resolve().parents[1] / "web" / "app.html").read_text(encoding="utf-8")
    block = re.search(r"function formatResult\(result\)\{(.*?)\n\}\nfunction fieldLabel", html, re.S)
    assert block, "formatResult renderer not found"
    source = block.group(1)

    expected = {
        "total_dynamic_head_m": "Total dynamic head",
        "total_dynamic_head_kpa": "Total dynamic head (kPa)",
        "total_dynamic_head_bar": "Total dynamic head (bar)",
        "total_dynamic_head_ft": "Total dynamic head (ft)",
        "total_dynamic_head_psi": "Total dynamic head (psi)",
    }
    for key, label in expected.items():
        assert f'{key}:"{label}"' in source
    assert 'total_dynamic_head_kpa:"Total dynamic head",' not in source
    assert 'total_dynamic_head_bar:"Total dynamic head",' not in source
    assert 'total_dynamic_head_ft:"Total dynamic head",' not in source
    assert 'total_dynamic_head_psi:"Total dynamic head",' not in source


def test_dashboard_renderer_has_generic_scalar_fallback():
    html = (Path(__file__).resolve().parents[1] / "web" / "app.html").read_text(encoding="utf-8")
    assert 'const scalarKeys=Object.keys(result).filter' in html
    assert 'scalarKeys.filter(k=>!preferred.includes(k))' in html
    assert 'labels[k]||humanize(k)' in html
