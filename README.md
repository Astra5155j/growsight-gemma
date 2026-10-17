# GrowSight — Local Gemma Website Growth Auditor

GrowSight is a local-first web app for business owners. Paste a public website URL and it:
- opens the site in Chromium,
- captures desktop and mobile screenshots,
- collects page structure and customer-journey signals,
- runs deterministic checks,
- asks **Gemma through Ollama** for prioritized, evidence-based website improvement ideas,
- optionally sends the screenshots to Gemma for visual feedback (Gemma 3 vision models support images),
- displays the report in a web dashboard and lets you download JSON.

It does **not** promise revenue increases. It identifies hypotheses that should be validated with analytics, user testing, or A/B tests.

## Requirements
- Python 3.11+
- Internet access to scan public websites
- Ollama installed and running
- A local vision-capable model such as `gemma3:4b`
- Playwright Chromium

## Fedora setup

From the extracted `growsight_gemma` directory:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
```

Make sure Ollama is running and Gemma is installed:

```bash
ollama list
ollama run gemma3:4b "Say GrowSight is ready"
```

Edit `.env` if needed. Defaults:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:4b
OLLAMA_TIMEOUT_SECONDS=180
SCAN_TIMEOUT_MS=30000
ENABLE_VISION=true
```

Start the app:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000.

## Test

1. Keep Ollama running.
2. Start GrowSight using the command above.
3. Paste `https://example.com` to test basic scanning, or try a real public business website.
4. Leave **Use Gemma AI** and **Analyze screenshots with vision** checked.
5. A successful AI report should say `Gemma via local Ollama` and show the model name.

## Project structure

```text
growsight_gemma/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── scanner.py
│   ├── audit.py
│   └── ollama_client.py
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── tests/
│   └── test_url_safety.py
├── .env.example
├── requirements.txt
└── README.md
```

## Safety and limitations
- Keep the app bound to `127.0.0.1`; do not expose it to the public internet without authentication, isolation, rate limits, and a security review.
- The scanner only accepts public HTTP(S) URLs and blocks requests to local/private/reserved IP addresses as a basic SSRF mitigation. This is not a guarantee against every DNS rebinding or browser-network attack.
- Scan only websites you own or have permission to assess.
- Some websites block automated browsers, require login, or load content in ways the scanner cannot see.
- Screenshots are temporarily returned to the browser session and are not saved to a server-side file.
- AI recommendations are hypotheses, not guaranteed revenue gains. To estimate actual business impact, connect analytics and test changes.
