# BugHound Mini Model Card (Reflection)

---

## 1) What is this system?

**Name:** BugHound
**Purpose:** Analyze a Python snippet, propose a minimal fix, and score the fix's risk before deciding whether it can be auto-applied.
**Intended users:** Students learning agentic workflows and AI reliability concepts; developers wanting a lightweight offline or Gemini-powered code review pass.

---

## 2) How does it work?

BugHound runs five steps: **Plan** (logs intent), **Analyze** (finds issues via heuristics or Gemini), **Act** (proposes a fix via heuristics or Gemini), **Test** (scores risk with `assess_risk`), and **Reflect** (decides whether to auto-apply). Heuristics handle everything offline; Gemini is called only when an API key is present and falls back to heuristics on any API error or unparseable output.

---

## 3) Inputs and outputs

**Inputs tested:**
- `cleanish.py` — a clean 5-line function with proper logging; no issues expected
- `mixed_issues.py` — a function with a bare `except:`, `print()`, and a `TODO` comment
- Comments-only snippet — no executable code, used as an edge case

**Outputs observed:**
- `cleanish.py`: zero issues, original code returned unchanged, risk=low, autofix=YES
- `mixed_issues.py`: three issues (Low/High/Medium), heuristic fix replaced `print` and `except:`, risk=high, autofix=NO
- Comments-only: zero issues, code returned unchanged, risk=low, autofix=YES (misleading but harmless)

---

## 4) Reliability and safety rules

**Rule 1 — Missing return statement (`-30`):** Checks whether `return` appears in the original but not the fix. Matters because silently dropping a return value changes behavior. False positive: a refactor that legitimately inlines the return (e.g., `return f(x)` → `f(x)` as last expression) would still fire.

**Rule 2 — Oversized fix blocked from autofix:** If the fix is >1.5× the original line count, `should_autofix` is forced to False regardless of score. Matters because LLMs often rewrite instead of patch, introducing unreviewed code. False negative: a genuinely minimal fix that adds many short lines (e.g., inline type annotations on every argument) would also be blocked.

---

## 5) Observed failure modes

1. **Oversized rewrite with unsafe confidence:** On `flaky_try_except.py` with only a Low severity issue, Gemini produced a 22-line rewrite of a 6-line function and the score landed at exactly 75 (the autofix threshold). Without the guardrail, this would auto-apply a full rewrite triggered by a minor issue.

2. **MockClient silently forces heuristic fallback:** `MockClient` intentionally returns non-JSON for the analyzer prompt, so every run in "Gemini mode" with MockClient silently falls back to heuristics with a log message — but the UI shows no warning to the user that the mode switched mid-run.

---

## 6) Heuristic vs Gemini comparison

Heuristics reliably catch the three patterns they are coded for (`print`, bare `except:`, `TODO`) but miss anything else. Gemini detects subtler issues such as missing type hints, implicit type coercion, or undocumented edge cases. Gemini-proposed fixes tend to be significantly larger (adding imports, docstrings, type annotations) while heuristic fixes are surgical regex substitutions. The risk scorer agreed with intuition on obvious cases but couldn't distinguish a Gemini over-engineering from a genuine minimal patch without the oversized guardrail.

---

## 7) Human-in-the-loop decision

**Scenario:** The fix changes control flow — a `return` is moved inside a conditional, or a new `if` branch is added that didn't exist before. These changes can alter behavior in ways that pass all current checks. The trigger should live in `risk_assessor`: detect when the number of `if`/`return` statements differs between original and fix, add a penalty, and always force `should_autofix=False`. The UI should show: *"Fix alters control flow — human review required before applying."*

---

## 8) Improvement idea

Load the prompt files (`prompts/analyzer_system.txt`, `prompts/fixer_system.txt`) at runtime instead of using shorter inline strings — which this session already implemented. The files include explicit severity constraints and "minimal changes" guidance that the inline prompts lacked, reducing the rate of non-compliant model output without touching any parsing or scoring logic.
