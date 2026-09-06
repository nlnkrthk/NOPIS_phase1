# C1 — Task 230: LLM integration for the Network Insight Generator.
#
# Sends one curated evidence object (Task 229, see services.get_evidence_object)
# to an LLM and requests a strictly evidence-grounded, four-section operational
# explanation.
#
# Two providers are supported behind the same generate_insight(evidence) call:
#   - Claude (Anthropic Messages API) — the intended production provider.
#   - NVIDIA NIM (OpenAI-compatible endpoint, openai/gpt-oss-20b) — a temporary
#     stand-in used to test the pipeline before a Claude API key is available.
#
# Provider selection is automatic: Claude is used whenever ANTHROPIC_API_KEY is
# set (real key can just be dropped into .env later, no code change needed),
# otherwise NVIDIA_API_KEY is used. All keys are read only from environment
# variables — never hardcoded and never printed/logged. A local .env file
# (see .env.example at the project root) is loaded automatically for local
# development; it is git-ignored so real keys never get committed.

import json
import os
from pathlib import Path

from dotenv import load_dotenv

# Load the nearest .env (project root) once, without overriding a variable the
# environment already provides (e.g. in production, where it is set directly).
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=False)

ANTHROPIC_MODEL = "claude-opus-5"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "openai/gpt-oss-20b"

# Kept for backwards compatibility with callers that display "Model: {MODEL}".
MODEL = ANTHROPIC_MODEL

SYSTEM_PROMPT = """You are a network operations analyst assistant for a telecom grid monitoring system.

You are given a single EVIDENCE OBJECT as JSON. It comes from two tables: grid_features
(activity measures derived from combined call, SMS and internet event counts for a grid) and
network_anomaly_scores (a statistical comparison of current activity to a historical baseline
for that same grid and timestamp).

SEVERITY DECISION RULE — apply this exactly; it is the ONLY policy you should use, so
never say a threshold or mapping is missing when "direction" and "anomaly_score" are both present:
- If "direction" is "NORMAL": SEVERITY is NORMAL.
- If "direction" is "HIGH" or "LOW" (the anomaly-detection pipeline already flagged this grid)
  AND the absolute value of "anomaly_score" is 100 or greater: SEVERITY is HIGH.
- If "direction" is "HIGH" or "LOW" AND the absolute value of "anomaly_score" is less than 100:
  SEVERITY is ATTENTION.
- This decision uses ONLY the "direction" and "anomaly_score" fields — no other field is needed
  to classify severity, so their presence alone is always sufficient.
- The ONLY time severity is genuinely undetermined is when "direction" and/or "anomaly_score" is
  completely ABSENT from the evidence object (not merely present with a value). In that exact
  case, say so explicitly in SEVERITY and name precisely which field(s) are missing — do not
  guess a severity level and do not default to NORMAL/ATTENTION/HIGH.

STRICT RULES — follow every one of these without exception:
1. The numbers in the evidence are ACTIVITY MEASURES (a composite indicator built from call, SMS
   and internet event counts). They are NOT call counts, message counts, megabytes, bandwidth,
   capacity, or utilization figures.
2. Never use the words "congestion", "bandwidth exhaustion", or "capacity exhaustion" anywhere in
   your response — not even to deny or rule them out. This evidence contains no capacity or
   utilization data of any kind, so those concepts are simply irrelevant here; do not raise the
   topic at all, in either direction.
3. Never invent, estimate, or assume a number, metric, or fact that is not literally present in
   the evidence object. If a field is absent from the evidence, say plainly that it is absent —
   never substitute zero, a typical value, or a guess for it.
4. Never state a confirmed root cause. Only offer clearly-labeled inference/speculation.
5. Keep EVIDENCE (facts only, taken verbatim from the input) strictly separate from
   INTERPRETATION (inference only, explicitly marked as such).
6. Apply the SEVERITY DECISION RULE above exactly as written — do not substitute your own
   thresholds, and do not treat an unstated "policy" or "mapping" as missing evidence when
   "direction" and "anomaly_score" are both present in the input.

Respond in EXACTLY this four-section plain-text format, using these exact section headings, in
this order, and nothing else before, between, or after them:

SEVERITY
NORMAL / ATTENTION / HIGH, decided strictly via the SEVERITY DECISION RULE above — or, only if
"direction" and/or "anomaly_score" is completely absent from the evidence, an explicit statement
that severity cannot be determined and exactly which of those two fields would be needed.

EVIDENCE
Only facts and numbers present in the input. No inference here.

INTERPRETATION
What the evidence might mean. Every claim here must be clearly marked as inference
(e.g. "This may indicate...", "One possible explanation is..."). Never state this as fact.

NEXTCHECKS
Concrete, specific things a human network engineer should inspect next, given this evidence.
"""


def _user_message(evidence: dict) -> str:
    return (
        "Here is the evidence object for one grid at one timestamp:\n\n"
        f"{json.dumps(evidence, indent=2)}\n\n"
        "Produce the SEVERITY / EVIDENCE / INTERPRETATION / NEXTCHECKS analysis."
    )


def _active_provider() -> str:
    """Claude is used whenever a real ANTHROPIC_API_KEY is configured; NVIDIA's
    OpenAI-compatible NIM endpoint is the stand-in until then. This means
    dropping the real Claude key into .env later switches providers with no
    code change."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("NVIDIA_API_KEY"):
        return "nvidia"
    raise RuntimeError(
        "Neither ANTHROPIC_API_KEY nor NVIDIA_API_KEY is set. Put one of them in "
        "the project-root .env file (see .env.example) or export it in your "
        "shell — keys are never read from source code or committed files."
    )


def current_model_name() -> str:
    """The model that generate_insight() would actually call right now, for
    display purposes (e.g. the "model" field on the /insight API response)."""
    return ANTHROPIC_MODEL if _active_provider() == "anthropic" else NVIDIA_MODEL


def _generate_via_anthropic(evidence: dict) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_message(evidence)}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def _generate_via_nvidia(evidence: dict) -> str:
    from openai import OpenAI

    client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=os.environ["NVIDIA_API_KEY"])
    completion = client.chat.completions.create(
        model=NVIDIA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_message(evidence)},
        ],
        temperature=1,
        top_p=1,
        max_tokens=4096,
        stream=False,
    )
    message = completion.choices[0].message
    # gpt-oss models separate their chain-of-thought into reasoning_content —
    # useful to see while testing, but only .content is the four-section
    # answer our callers parse, so that's the only part returned.
    reasoning = getattr(message, "reasoning_content", None)
    if reasoning:
        print(f"[claude_insight_service] NVIDIA reasoning_content:\n{reasoning}\n")
    return (message.content or "").strip()


def generate_insight(evidence: dict) -> str:
    """Send one evidence object to the active LLM provider and return its
    four-section response text."""
    if _active_provider() == "anthropic":
        return _generate_via_anthropic(evidence)
    return _generate_via_nvidia(evidence)
