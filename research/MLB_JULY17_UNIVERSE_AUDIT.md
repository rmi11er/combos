# July 17 native seller audit

Full-row Decimal audit passed: 292,887 native rows, 258,546 YES prints. Scenario net P&L: $314,348.30; maker fees: $241,266.53. This is observed-public-price unlimited selling, not an RFQ fill or funded return. Historical fee applicability remains unverified.

Largest positive fixture membership: 26JUL172010SDKC; removing its prints leaves $-802,486.08. Memberships overlap and are not additive attribution.

Two market definitions have result `scalar` with an explicit zero-dollar settlement. The initial audit incorrectly required every endpoint payout to have a binary result label. It now checks and retains the explicit scalar payout, counts affected prints, and passes without changing native data or production P&L.

Evidence: [verification](../runs/morning_research_20260908/universe_july17_audit/verification.json).
