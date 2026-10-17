from __future__ import annotations

import json
import os

import httpx


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


async def analyze_with_gemma(report: dict, analyze_screenshots: bool = True) -> dict:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
    timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
    enable_vision = os.getenv("ENABLE_VISION", "true").lower() in {"1", "true", "yes"}

    signals = report.get("page_signals", {})
    compact_evidence = {
        "url": report.get("scanned_url"),
        "title": signals.get("title"),
        "meta_description": signals.get("meta_description"),
        "headings": signals.get("headings", [])[:15],
        "buttons": signals.get("buttons", [])[:25],
        "images": signals.get("images", {}),
        "signals": signals.get("signals", {}),
        "rule_findings": report.get("findings", [])[:10],
    }

    prompt = f"""You are GrowSight, a careful website conversion and usability consultant for small businesses.
Analyze the supplied website evidence and, if images are attached, the desktop/mobile screenshots.
Give practical, specific improvements. Focus on visual hierarchy, clarity of the offer, mobile usability,
calls to action, trust, pricing clarity, friction, and features that suit the apparent business.
Do not invent analytics, customer demographics, company facts, or conversion rates.
Never promise revenue growth. Describe impact as a hypothesis that should be tested.
If the page looks like a placeholder/demo, say that clearly and recommend testing a real business website.
Return ONLY valid JSON using this exact shape:
{{
  "executive_summary": "2-4 sentences",
  "opportunities": [
    {{
      "priority": "High|Medium|Low",
      "title": "short action-oriented title",
      "evidence": "what you observed; distinguish observation from uncertainty",
      "recommendation": "specific visual or functional change",
      "why_it_may_help": "plausible non-guaranteed business rationale",
      "effort": "Low|Medium|High",
      "success_metric": "what the owner should measure"
    }}
  ],
  "suggested_features": [
    {{
      "feature": "feature name",
      "reason": "why it may fit this site",
      "effort": "Low|Medium|High"
    }}
  ],
  "questions_for_owner": ["up to 3 questions that would make the audit more accurate"]
}}
Limit opportunities to 6 and suggested_features to 4.
Evidence collected by the scanner:
{json.dumps(compact_evidence, ensure_ascii=False)}
"""
    images = []
    if analyze_screenshots and enable_vision:
        shots = report.get("screenshots", {})
        if shots.get("desktop_jpeg_base64"):
            images.append(shots["desktop_jpeg_base64"])
        if shots.get("mobile_jpeg_base64"):
            images.append(shots["mobile_jpeg_base64"])

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=5.0)) as client:
            # Gemma 3 supports image inputs via Ollama's `images` field.
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            }
            if images:
                payload["images"] = images[:2]
            response = await client.post(f"{base_url}/api/generate", json=payload)
            response.raise_for_status()
            raw = response.json().get("response", "")
        parsed = _extract_json(raw)
        report["ai"] = {
            "used": True,
            "provider": "Gemma via local Ollama",
            "model": model,
            "status": "success",
            "vision_used": bool(images),
        }
        report["ai_summary"] = str(parsed.get("executive_summary", ""))[:2000]
        report["ai_opportunities"] = parsed.get("opportunities", [])[:6]
        report["suggested_features"] = parsed.get("suggested_features", [])[:4]
        report["questions_for_owner"] = parsed.get("questions_for_owner", [])[:3]
    except httpx.ConnectError:
        report["ai"] = {
            "used": False, "provider": "Ollama", "model": model,
            "status": "Ollama not reachable. Start Ollama and retry.",
            "error": f"Could not connect to {base_url}.",
        }
    except httpx.TimeoutException:
        report["ai"] = {
            "used": False, "provider": "Ollama", "model": model,
            "status": "Gemma timed out. Try again or use a smaller model.",
            "error": f"Request exceeded {timeout} seconds.",
        }
    except Exception as exc:
        report["ai"] = {
            "used": False, "provider": "Ollama", "model": model,
            "status": "Gemma analysis failed; rule-based findings are still available.",
            "error": f"{type(exc).__name__}: {str(exc)[:250]}",
        }
    return report
