from reliability.risk_assessor import assess_risk


def test_no_fix_is_high_risk():
    risk = assess_risk(
        original_code="print('hi')\n",
        fixed_code="",
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "print"}],
    )
    assert risk["level"] == "high"
    assert risk["should_autofix"] is False
    assert risk["score"] == 0


def test_low_risk_when_minimal_change_and_low_severity():
    original = "import logging\n\ndef add(a, b):\n    return a + b\n"
    fixed = "import logging\n\ndef add(a, b):\n    return a + b\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "minor"}],
    )
    assert risk["level"] in ("low", "medium")  # depends on scoring rules
    assert 0 <= risk["score"] <= 100


def test_high_severity_issue_drives_score_down():
    original = "def f():\n    try:\n        return 1\n    except:\n        return 0\n"
    fixed = "def f():\n    try:\n        return 1\n    except Exception as e:\n        return 0\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[{"type": "Reliability", "severity": "High", "msg": "bare except"}],
    )
    assert risk["score"] <= 60
    assert risk["level"] in ("medium", "high")


def test_missing_return_is_penalized():
    original = "def f(x):\n    return x + 1\n"
    fixed = "def f(x):\n    x + 1\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[],
    )
    assert risk["score"] < 100
    assert any("Return" in r or "return" in r for r in risk["reasons"])


def test_oversized_fix_blocks_autofix_even_at_low_severity():
    # Failure mode: a Low severity issue triggers an LLM rewrite 3-4x larger than the
    # original. Without the oversized guardrail, score stays at "low" and autofix fires.
    # With the guardrail, should_autofix must be False regardless of score level.
    original = (
        "def load_data(path):\n"
        "    try:\n"
        "        data = open(path).read()\n"
        "    except:\n"
        "        return None\n"
        "    return data\n"
    )
    # Simulate a verbose LLM rewrite: 22 lines vs 6 original (3.7x)
    oversized_fix = "\n".join([
        "import logging",
        "from pathlib import Path",
        "from typing import Optional",
        "",
        "logger = logging.getLogger(__name__)",
        "",
        "def load_data(path: str) -> Optional[str]:",
        '    """Load data from a file path."""',
        "    file_path = Path(path)",
        "    if not file_path.exists():",
        '        logger.warning("File not found: %s", path)',
        "        return None",
        "    if not file_path.is_file():",
        '        logger.warning("Not a file: %s", path)',
        "        return None",
        "    try:",
        "        data = file_path.read_text()",
        '        logger.info("Loaded %d bytes from %s", len(data), path)',
        "        return data",
        "    except Exception as e:",
        '        logger.error("Failed to read %s: %s", path, e)',
        "        return None",
    ]) + "\n"

    risk = assess_risk(
        original_code=original,
        fixed_code=oversized_fix,
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "bare except"}],
    )

    assert risk["should_autofix"] is False, (
        "Oversized fix (>1.5x original lines) must not be auto-applied, "
        f"even at score={risk['score']} level={risk['level']}"
    )
    assert any("rewrite" in r.lower() or "substantial" in r.lower() for r in risk["reasons"])
