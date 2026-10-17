from __future__ import annotations

from datetime import datetime, timezone


def make_rule_audit(url: str, scan: dict) -> dict:
    findings = []

    def add(priority, title, evidence, recommendation, why, effort="Low"):
        findings.append({
            "priority": priority,
            "title": title,
            "evidence": evidence,
            "recommendation": recommendation,
            "why_it_may_help": why,
            "effort": effort,
            "source": "Automated page checks",
        })

    if not scan.get("title"):
        add("High", "Give the page a clear title", "No document title was detected.",
            "Add a concise title describing the business and this page's purpose.",
            "A clear title helps people understand the page and can improve search result clarity.")
    if not scan.get("meta_description"):
        add("Medium", "Write a search-result description", "No meta description was detected.",
            "Add an accurate description of the offer and who it is for.",
            "A useful snippet may help the right visitors choose your page from search results.")
    h1 = [h for h in scan.get("headings", []) if h.get("tag") == "h1"]
    if not h1:
        add("High", "Make the main offer obvious", "No H1 heading was detected.",
            "Add a clear headline saying what the business offers and who it helps.",
            "Visitors should quickly understand why the page is relevant to them.")
    elif len(h1) > 1:
        add("Low", "Review the headline hierarchy", f"{len(h1)} H1 headings were detected.",
            "Check that the page has one clear primary headline and a sensible heading hierarchy.",
            "A clear hierarchy makes the page easier to scan.")
    signals = scan.get("signals", {})
    if not signals.get("viewport_meta"):
        add("High", "Check mobile responsiveness", "No viewport meta tag was detected.",
            "Add a responsive viewport declaration and test important pages on narrow screens.",
            "A page that is awkward on phones can make it harder for customers to act.")
    if signals.get("horizontal_overflow") or signals.get("mobile_horizontal_overflow"):
        add("High", "Fix horizontal scrolling", "The page appears wider than its viewport on desktop or mobile.",
            "Inspect fixed-width blocks, large tables, images, and navigation and make them responsive.",
            "Unexpected sideways scrolling can hide content and interrupt the customer journey.", "Medium")
    if not signals.get("has_primary_action"):
        add("High", "Make the next step unmistakable", "No common primary action label was detected.",
            "Add a prominent action that fits the business, such as Book, Order, Get a Quote, or Contact.",
            "Visitors should not have to guess what to do next.")
    if not signals.get("has_contact_terms"):
        add("Medium", "Make contact details easy to find", "Common contact terms were not detected.",
            "Add a visible contact page and the best contact method for customers.",
            "Easy-to-find contact details can reduce uncertainty before a purchase or enquiry.")
    if not signals.get("has_trust_terms"):
        add("Medium", "Add genuine trust signals", "Common review, testimonial, or case-study terms were not detected.",
            "If available, show genuine reviews, relevant credentials, transparent policies, or case studies.",
            "Relevant evidence can help customers feel more confident.")
    images = scan.get("images", {})
    if images.get("missing_alt", 0):
        add("Medium", "Improve image accessibility", f"{images['missing_alt']} image(s) have no alt attribute.",
            "Add concise alt text to meaningful images; use empty alt text for purely decorative images.",
            "This helps people using assistive technology understand meaningful images.")
    if signals.get("body_word_count", 0) < 80:
        add("Medium", "Explain the offer and process", f"Only about {signals.get('body_word_count', 0)} words were detected.",
            "Explain the offer, who it is for, what it costs or how quotes work, and what happens next.",
            "Visitors need enough information to decide whether to take the next step.")
    if not signals.get("has_price_terms"):
        add("Low", "Reduce price uncertainty", "No common pricing terms or currency symbols were detected.",
            "Where practical, show prices, starting prices, package examples, or explain how quotes work.",
            "Clear expectations may help qualified visitors decide whether to enquire.", "Medium")
    if not findings:
        add("Low", "Validate the customer journey", "Basic automated checks did not find an obvious issue.",
            "Ask a few real customers to complete the main task and review analytics for drop-off points.",
            "Automated checks cannot establish how well a page converts.")

    findings.sort(key=lambda x: {"High": 0, "Medium": 1, "Low": 2}.get(x["priority"], 3))
    return {
        "product": "GrowSight",
        "url": url,
        "scanned_url": scan.get("final_url", url),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": "The report highlights observable website issues and improvement hypotheses. Revenue impact must be measured.",
        "findings": findings[:12],
        "page_signals": {
            "title": scan.get("title", ""),
            "meta_description": scan.get("meta_description", ""),
            "headings": scan.get("headings", []),
            "buttons": scan.get("buttons", []),
            "images": scan.get("images", {}),
            "signals": scan.get("signals", {}),
            "warnings": scan.get("warnings", []),
        },
        "screenshots": scan.get("screenshots", {}),
        "ai": {
            "used": False,
            "provider": "Ollama",
            "model": None,
            "status": "Rule-based audit prepared; AI not run yet",
        },
    }
