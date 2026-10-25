# API inventory

Checked 2026-09-09. This distinguishes **documented contracts**, **repository fixtures**, and **live requests**. No authenticated TBA or FIRST data request was made; no credentials were requested or used. 2026 illustrates the season-specific fields.

## Services at a glance

| Service | What it supplies | Access | What it does not establish |
|---|---|---|---|
| The Blue Alliance | Events, teams, matches, results, score breakdowns, rankings, videos/webcasts, estimated ratings; optional timeseries and Zebra | API v3; `X-TBA-Auth-Key` | Per-robot fuel attempts/makes, cycles, or defense truth |
| FIRST FRC Events | FMS-synchronized official event schedules and results, season score details | Published collection uses v3.0; HTTP Basic username + authorization key | A live in-match action stream or universal per-robot scoring ledger |
| Statbotics | EPA, rankings and match predictions derived from match data | Public v3 REST; Python client | Independently observed per-robot actions |
| YouTube Data API | Video and channel metadata, duration, availability-related fields, live metadata | API project/key for applicable public reads; OAuth for restricted operations | Raw downloadable footage, robot tracks, or scouting statistics |
| Nexus / TBA Nexus cache | Event queuing/status context | Direct Nexus access separate; TBA cached endpoint uses TBA key | Scoring-event or robot-telemetry truth |

Primary references: [TBA schema](https://github.com/the-blue-alliance/the-blue-alliance/blob/4d7b599c56b2f2c21a85ea03e6db9c06ed8ec942/src/backend/web/static/swagger/api_v3.json), [FIRST documentation](https://frc-api-docs.firstinspires.org/), [Statbotics OpenAPI](https://api.statbotics.io/openapi.json), [YouTube reference](https://developers.google.com/youtube/v3/docs), [Nexus](https://frc.nexus/en/api).

## The Blue Alliance

Base: `https://www.thebluealliance.com/api/v3`. The inspected OpenAPI version is `3.26.0`. Use the full match endpoint when score breakdowns and video references are needed; `/simple` and `/keys` variants are intentionally reduced.

| GET path | Useful data | AutoScout use |
|---|---|---|
| `/status` | API/data status | Diagnose service/data readiness |
| `/events/{year}` | Event catalog | Find competitions |
| `/event/{event_key}` | Event details, webcasts, FIRST event code | Discover sources and map services |
| `/event/{event_key}/teams` | Participating teams | Team roster |
| `/event/{event_key}/matches` | Full match objects | Bulk ingest per event |
| `/match/{match_key}` | One full match | Re-fetch posted/corrected results |
| `/team/{team_key}/event/{event_key}/matches` | Team's event matches | Team report/video queue |
| `/event/{event_key}/rankings` | Official event rankings as represented by TBA | Event context |
| `/event/{event_key}/alliances` | Alliance selection | Playoff context |
| `/event/{event_key}/oprs` | OPR/DPR/CCWM estimates | Labeled statistical baseline |
| `/event/{event_key}/coprs` | Component OPR estimates | Labeled component baseline |
| `/match/{match_key}/zebra_motionworks` | Optional timestamped team positions | Trajectory comparison |
| `/event/{event_key}/matches/timeseries` | Match keys with optional timeseries | Availability discovery |
| `/match/{match_key}/timeseries` | Game-specific unofficial timeseries | Exploratory synchronization only |
| `/event/{event_key}/nexus_info` | Cached Nexus context or null | Queuing context |

All paths above were checked against the [pinned schema](https://github.com/the-blue-alliance/the-blue-alliance/blob/4d7b599c56b2f2c21a85ea03e6db9c06ed8ec942/src/backend/web/static/swagger/api_v3.json). Their presence does not guarantee populated responses at every event.

### Match context and video references

Retain `key`, `event_key`, `comp_level`, `set_number`, `match_number`, alliance `team_keys`, `surrogate_team_keys`, `dq_team_keys`, and alliance `score`. An unplayed alliance score is documented as `-1`. `score_breakdown` can be null.

`time`, `actual_time`, `predicted_time`, and `post_result_time` are nullable UNIX timestamps with different meanings. None is a video-frame offset. Broadcast latency, introductions, replays, and edits must be handled separately.

`videos[]` supplies `{type, key}` references, not video bytes or calibration. Event `webcasts[]` identifies provider/channel and optional status information. A match may have no video or several references. **Inference:** deduplicate source processing and persist a separate match-time/video-time alignment record.

### Exact 2026 score fields

Within `score_breakdown.red` or `.blue`:

| Field group | Fields | Granularity |
|---|---|---|
| Auto tower | `autoTowerRobot1`, `autoTowerRobot2`, `autoTowerRobot3`, `autoTowerPoints` | Robot station outcomes plus alliance points |
| Endgame tower | `endGameTowerRobot1`, `endGameTowerRobot2`, `endGameTowerRobot3`, `endGameTowerPoints` | Robot station outcomes plus alliance points |
| Fuel | `hubScore` | Alliance, with phase/shift subdivisions |
| Aggregate points | `totalAutoPoints`, `totalTeleopPoints`, `totalTowerPoints`, `totalPoints` | Alliance |
| Fouls/adjustment | `foulPoints`, `adjustPoints`, `majorFoulCount`, `minorFoulCount`, `g206Penalty` | Alliance fields; not a per-robot foul ledger |
| Bonuses | `energizedAchieved`, `superchargedAchieved`, `traversalAchieved`, `rp` | Alliance outcome |

The shared tower enum is `None`, `Level1`, `Level2`, `Level3`. Do not interpret enum membership as proof that every outcome is legal in every phase. Robot1/2/3 are station-indexed outcomes; preserve alliance order and verify station mapping when joining upstream FIRST data. Never sort the roster numerically before mapping these fields.

`hubScore` documents each pair below:

| Segment | Count | Points |
|---|---|---|
| Auto | `autoCount` | `autoPoints` |
| Transition | `transitionCount` | `transitionPoints` |
| Shift 1 | `shift1Count` | `shift1Points` |
| Shift 2 | `shift2Count` | `shift2Points` |
| Shift 3 | `shift3Count` | `shift3Points` |
| Shift 4 | `shift4Count` | `shift4Points` |
| Endgame | `endgameCount` | `endgamePoints` |
| Teleop aggregate | `teleopCount` | `teleopPoints` |
| Match aggregate | `totalCount` | `totalPoints` |

Compare corresponding **counts to counts**, and points to points. Do not sum aggregate fields again with their component shifts. Do not assume every visually observed hub entry contributes to these fields: define game-rule eligibility and handling of delayed/uncounted entries explicitly. No field here names the shooter of an individual fuel score. [2026 schema definitions](https://github.com/the-blue-alliance/the-blue-alliance/blob/4d7b599c56b2f2c21a85ea03e6db9c06ed8ec942/src/backend/web/static/swagger/api_v3.json)

### Fixture-backed example and schema drift

TBA's checked-in `2026marea_matches.json` contains `2026marea_f1m1`. Its red alliance has fuel `totalCount=330`, `totalPoints=330`, `foulPoints=20`, and overall `totalPoints=350`. Thus a vision fuel counter should not be compared to 350 as if all points were fuel. The same fixture includes `hubScore.uncounted` and alliance `penalties`, which are absent from the inspected 2026 schema's declared properties. Preserve unknown fields and record schema provenance; do not invent semantics for undocumented fields. This is a repository fixture, not a fresh authenticated result. [Pinned fixture](https://github.com/the-blue-alliance/the-blue-alliance/blob/4d7b599c56b2f2c21a85ea03e6db9c06ed8ec942/src/backend/common/helpers/tests/data/2026marea_matches.json)

### Optional feeds are not interchangeable

**Zebra MotionWorks:** the schema supplies `times[]` and, for each team, `team_key`, `xs[]`, and `ys[]`. Coordinates are documented in feet, with missing samples represented by nulls. These can support position/trajectory validation if the target match actually has data. Coverage, camera alignment, and measurement quality must be checked. No 2026 coverage census was performed.

**Match timeseries:** TBA explicitly describes this as unofficial, potentially erroneous or missing, and under active development. The event endpoint only lists available match keys. The match response is a generic array; the schema still includes a historical 2018-specific model. **No evidence here establishes a complete 2026 live scoring timeline.** Do not use it as ground truth. Also do not confuse season-level insights timeseries with in-match telemetry. [Endpoint contracts](https://github.com/the-blue-alliance/the-blue-alliance/blob/4d7b599c56b2f2c21a85ea03e6db9c06ed8ec942/src/backend/web/static/swagger/api_v3.json)

### Updates and caching

Respect response `Cache-Control` and `ETag`; use `If-None-Match` for conditional reads. Webhooks can announce `upcoming_match`, `match_score`, and `match_video`. They require account setup and verification; requests carry `X-TBA-HMAC`. Treat a notification as a trigger to update stored data, with idempotent processing and score-revision history. This pass did not configure a webhook or establish a live delivery latency. [Webhook documentation](https://www.thebluealliance.com/apidocs/webhooks)

## FIRST FRC Events API

The official documentation's linked Postman collection currently lists `https://frc-api.firstinspires.org/v3.0/`. Older examples elsewhere use v2.0; pin the contract selected for implementation. The documentation itself retains some older explanatory prose and score examples, so do not assume every example reflects the current season.

| GET path relative to `/v3.0` | Purpose |
|---|---|
| `/{season}/events` | Event listings, with filters |
| `/{season}/teams` | Teams, with event/team filters and pagination |
| `/{season}/schedule/{eventCode}` | Schedule; use documented tournament/team filters |
| `/{season}/matches/{eventCode}` | Posted match results |
| `/{season}/scores/{eventCode}/{tournamentLevel}` | Season-specific score details |
| `/{season}/rankings/{eventCode}` | Event rankings |
| `/{season}/alliances/{eventCode}` | Alliance selection |
| `/{season}/awards/event/{eventCode}` | Event awards |

Authentication is HTTP Basic with base64 of `username:authorizationKey`. Conditional reads use `Last-Modified`/`If-Modified-Since`; the documented `FMS-OnlyModifiedSince` option returns only changed portions and must not be combined with `If-Modified-Since`.

The documentation says FMS does not synchronize while a match is running and the results API cannot supply an in-progress match. Venue connectivity can delay publication. TBA and FIRST generally reflect the same underlying scoring process, so comparing both can diagnose ingestion disagreement but does not supply independent robot-attribution labels.

The fetched Score Details section offered examples through 2024, not a 2026 example. This pass therefore uses TBA's 2026 schema/fixture for exact 2026 fields and does **not** claim a live FIRST 2026 response was verified. [Official docs](https://frc-api-docs.firstinspires.org/) · [Published collection](https://frc-api-docs.firstinspires.org/api/collections/13920602/TW6zHTEi?segregateAuth=true&versionTag=latest)

## Statbotics

Base: `https://api.statbotics.io/v3`. The loaded public OpenAPI lists single/list endpoints for `year(s)`, `team(s)`, `team_year(s)`, `event(s)`, `team_event(s)`, and `match(es)`.

Useful examples: `/team_year/{team}/{year}`, `/team_event/{team}/{event}`, and `/match/{match}`. List paths expose filtering/pagination parameters; use those documented per path. A `team_match` table exists in repository descriptions, but no `/v3/team_match...` route appears in the inspected public OpenAPI. Do not infer a public endpoint from an internal model. [OpenAPI](https://api.statbotics.io/openapi.json)

The repository serializers expose `epa.total_points`, `epa.breakdown`, ranks, and records for team-year data; event EPA statistics for team-events; and `pred` versus `result` for matches. Breakdowns vary by year. These are expected contributions/predictions, not measured actions. [Team-year serializer](https://github.com/avgupta456/statbotics/blob/a2cea5553e35693d423400f419bd770cb2143408/backend/src/db/models/team_year.py) · [Match serializer](https://github.com/avgupta456/statbotics/blob/a2cea5553e35693d423400f419bd770cb2143408/backend/src/db/models/match.py)

**Observed availability:** OpenAPI retrieval succeeded, while `GET /v3/team_year/254/2026` returned HTTP 500 on 2026-09-09. One failed sample does not prove every endpoint is down. The repository recommends CSV exports for large data-science work; this pass did not verify an available current-season export. Treat Statbotics as optional enrichment with an explicit unavailable state.

## Video and event timing APIs

**YouTube:** `videos.list` can resolve known video IDs into metadata; playlist/channel endpoints help discover uploads. Metadata access is separate from acquiring decodable video. TBA references and YouTube Data API responses do not provide a general raw-video download endpoint. Local recording uploads or a separately validated video-acquisition workflow remain necessary. [Video endpoint](https://developers.google.com/youtube/v3/docs/videos/list) · [API resource inventory](https://developers.google.com/youtube/v3/docs)

**Nexus:** TBA's `/event/{event_key}/nexus_info` documents a cached optional event object. Nexus also publishes an API page, but that page did not expose a readable contract in the browsing tool; direct authentication, limits, and endpoint details are not asserted here. Castle contains a Nexus integration and can be inspected in a later integration pass. This feed is useful for queue context, not shot validation. [Nexus page](https://frc.nexus/en/api) · [Castle integration](https://github.com/Team334/Castle/blob/392839d4476c2867edeee87dd7a7a8febc9bc466/app/scout/nexus.py)

No inspected public API supplies a universal per-frame six-robot identity stream, per-robot fuel attempt/miss ledger, or labeled video benchmark.
