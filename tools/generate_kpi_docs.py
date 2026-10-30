"""Regenerate the KPI section of README.md from services/kpi_registry.py."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.kpi_registry import KPIS, TREAT  # noqa: E402

BEGIN, END = "<!-- KPI-DOCS:BEGIN -->", "<!-- KPI-DOCS:END -->"
GROUPS = [("recruitment", "Recruitment"), ("employee", "Employees and turnover"), ("training", "Training"),
          ("performance", "Performance management (PMS)"), ("relations", "Employee relations and engagement"),
          ("change", "Comparison and change")]


def render() -> str:
    out = [BEGIN, "", "_Generated from `services/kpi_registry.py` — do not edit by hand. "
           "All examples use fictional numbers and are not workbook data._", ""]
    for ds, title in GROUPS:
        out += [f"### {title}", "", f"**Default treatment of missing/duplicate/invalid records:** {TREAT[ds]}", ""]
        for k in (k for k in KPIS if k["dataset"] == ds):
            src = "Sheet(s) classified as '" + ds + "' (see Data Explorer)" if ds != "change" else "Any metric above"
            out += [f"#### {k['name']}  (`{k['key']}`)", "",
                    f"1. **Business meaning:** {k['meaning']}",
                    f"2. **Formula:** `{k['formula']}`",
                    f"3. **Numerator:** {k['numerator']}",
                    f"4. **Denominator:** {k['denominator']}",
                    f"5. **Required columns:** {k['columns']}",
                    f"6. **Source:** {src}",
                    f"7. **Aggregation level / grain:** {k['grain']}",
                    f"8. **Reporting period:** {k['period']}",
                    f"9. **Missing/duplicate/invalid handling:** {k['treatment']}",
                    f"10. **Definition status:** {k['standard']}",
                    f"11. **Example (fictional):** {k['example']}", ""]
    out.append(END)
    return "\n".join(out)


def main() -> None:
    p = ROOT / "README.md"
    text = p.read_text(encoding="utf-8")
    new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: render(), text, flags=re.S)
    p.write_text(new, encoding="utf-8")
    print("KPI docs regenerated:", len(KPIS), "entries")


if __name__ == "__main__":
    main()
