# a-stock-data integration

Source: https://github.com/simonlin1212/a-stock-data

Local install path:

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7897'
$env:HTTPS_PROXY='http://127.0.0.1:7897'
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" --repo simonlin1212/a-stock-data --path . --name a-stock-data
```

Installed locally on 2026-07-08 as:

```text
C:\Users\sora5\.codex\skills\a-stock-data
```

## Role

Use `nga-alang-investing-notes` for Alang source retrieval, timeline, and interpretation.
Use `a-stock-data` as a market data verification layer for A-share questions.

Typical combined workflow:

1. Retrieve Alang's latest or historical view from `nga-alang-investing-notes`.
2. Use `a-stock-data` to check current market evidence, such as price action, volume, market cap, PE/PB, fund flow, limit-up pools, announcements, research reports, interactive Q&A, margin data, and Dragon-Tiger list data.
3. Separate Alang's quoted or summarized view from the assistant's market inference.

## Usage Boundary

`a-stock-data` depends on public market data endpoints and may be affected by rate limits, API changes, or temporary source failures. Treat it as a verification and screening helper, not as a trading signal by itself.

When Eastmoney endpoints are involved, avoid high-frequency repeated calls and prefer small, targeted checks.
