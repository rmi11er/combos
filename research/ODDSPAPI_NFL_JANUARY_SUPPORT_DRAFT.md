# Draft for OddsPapi support — not sent

We have an active American-football subscription (`sportId=14`) for `pinnacle+30`, with a 100,000-request allowance. We are trying to retrieve full-game, non-player historical Pinnacle odds for the first two rounds of the 2025 NFL season playoffs in January 2026. Your historical-odds documentation says history is available since January 2026, and the quota documentation describes historical requests as free.

The fixture catalog request below returned all ten games with the expected NFL tournament, teams and completed status:

```
GET /v4/fixtures?sportId=14&tournamentId=31&statusId=2&from=2026-01-10T00:00:00Z&to=2026-01-19T23:59:59Z&language=en
```

For each returned native fixture ID we then requested:

```
GET /v4/historical-odds?fixtureId=<fixture-id>&bookmakers=pinnacle%2B30
```

All ten returned HTTP 404 with this response:

```json
{"error":{"message":"No historical odds found.","code":"NOT_FOUND","details":"Please check the provided filters and try again."}}
```

| Fixture | Native fixture ID |
|---|---|
| Rams at Panthers, January 10 | `id1400003167432516` |
| Packers at Bears, January 10 | `id1400003167432512` |
| Bills at Jaguars, January 11 | `id1400003167432602` |
| 49ers at Eagles, January 11 | `id1400003167432514` |
| Chargers at Patriots, January 11 | `id1400003167432600` |
| Texans at Steelers, January 12 | `id1400003167441866` |
| Bills at Broncos, January 17 | `id1400003167434542` |
| 49ers at Seahawks, January 17 | `id1400003167426014` |
| Texans at Patriots, January 18 | `id1400003167426010` |
| Rams at Bears, January 18 | `id1400003167426012` |

For the first fixture, a separate request using `bookmakers=pinnacle` returned HTTP 403:

```json
{"error":{"message":"Restricted bookmaker(s).","code":"RESTRICTED_ACCESS","details":"Restricted bookmakers: pinnacle. You do not have access to these bookmakers."}}
```

Could you clarify whether the January archive exists under a different authorized historical bookmaker slug, whether `pinnacle+30` history starts later than January, or whether historical Pinnacle access needs to be enabled separately? If the undelayed archive is accessible to delayed-feed subscribers, what is the correct request or entitlement? We can apply the 30-second delay ourselves for research; we are not seeking unauthorized live undelayed access. Please also clarify whether historical `createdAt` is the original bookmaker information time or already includes the delayed feed's availability, and the currency/unit of historical `limit` values.

Separately, a prior MLB historical request with `pinnacle+30` returned HTTP 403 stating that sport 13 was not included in our subscription. That is a different response from these NFL January 404s. We want to understand the difference between free historical request accounting, bookmaker/sport authorization, and actual date coverage before changing a subscription.

Evidence was captured September 7, 2026 UTC. Requests and redacted responses are retained locally under `runs/nfl_playoffs_history_20260907/pinnacle/`; the final account snapshot showed 28 football requests used, up from 27 before discovery. One transient rate limit was retried after waiting; all ten final fixture responses were 404. No keys, account identifiers or authentication headers are included in this draft.
