# Record the 30-minute walkthrough

The chapter times below are **editorial estimates**, including code explanation, screen demonstrations and pauses. The narration files are prepared spoken passages, not 30 minutes of continuous speech. No finished audio/video or measured runtime is claimed.

Use the offline route immediately. Record cloud-specific claims only after completing the cloud lab and capturing genuine evidence. Until then, call those sections a code walkthrough, keep an **Integration not yet executed** label visible, and use conditional wording from the scripts.

## Prepare the screen

Use 1920×1080, 16:9, 30 fps. Increase terminal/editor font size; show one relevant function or query at a time. Hide account menus, shell history containing secrets, `.env`, secret values, notifications and unrelated tabs. Keep the terminal command and its output in the same shot. Use the project name without adding unrelated channel branding.

## Chapter and recording directions

| Time | Clip | Screen action | What viewers should understand |
| --- | --- | --- | --- |
| 00:00–02:00 | C01 | Run `python3 -m pipeline.local demo`; show four metrics and README diagram | Business question, result, local/cloud boundary |
| 02:00–05:30 | C02 | Open fixture, SQL schema, one customer document; show source setup guide | Order vs line vs payment grain, nested source data, private connectivity |
| 05:30–09:30 | C03 | Open `jobs/extract_sources.py`; inspect one local raw manifest/file | Real JDBC API choice, frozen snapshot, immutable batch/attempt IDs |
| 09:30–12:30 | C04 | Run the missing-file example in GETTING_STARTED; show empty ledger before recovery | Completion and integrity checks precede publication |
| 12:30–17:30 | C05 | Open quality rules, test output and Spark join; calculate 2×500−100 plus 300 | Exact money, duplicate conflicts, quarantine, grain-safe joins |
| 17:30–21:00 | C06 | Inspect stage/COPY loader; show Snowflake evidence only when available | Selected files, staging counts, pre-created objects |
| 21:00–24:30 | C07 | Run customer change; query versions and fact keys; run rollback test | Observed SCD2, original fact attribution, atomic watermarks, replay |
| 24:30–28:00 | C08 | Inspect generated ASL and DAG; show real terminal failure when integrated | Orchestrator responsibilities, persistent lock and deliberate recovery |
| 28:00–30:00 | C09 | Show KPI SQL/Power BI instructions; compare real report if built; teardown | Reconciliation, honest scope, reproducible repository |

## Capture checklist per chapter

1. Read the matching voiceover file once, then rehearse the command sequence.
2. Record a clean screen take showing actual results. Keep waits in the master recording; label shortened waits in the edit.
3. Record narration as `C01.wav` through `C09.wav` into the ignored root `voiceover/` directory. Leave natural pauses where a query result needs reading time.
4. Note the take name, actual clip duration and any wording changes in ignored production notes.
5. Match picture timing to measured audio. Do not label estimated chapter times as final subtitles.
6. Listen at joins, review dense code shots at normal playback size, and verify the ending survives the final export.

For a local-only video, explicitly state that AWS/Snowflake sections review supplied code. Do not splice local output into a cloud console shot or imply a deployment ran. For a full cloud video, replace all conditional narration with measured observations only after evidence exists.

## Demonstration commands

```bash
python3 -m pipeline.local demo
python3 -m pipeline.local customer-change
python3 -m unittest discover -s tests -v
python3 scripts/build_state_machine.py
python3 scripts/package_cloud.py
```

Use a fresh `--root .runtime/rehearsal-01` for each full rehearsal. Pass that same root to both demo and customer-change commands. Run the source/cloud setup ahead of recording instead of promising every installation in the 30-minute edit.

## Publishing text

Suggested title: **End-to-End Data Engineering Project: Batch Pipelines, Replay and Customer History**.

Description opening: “Build and test an e-commerce batch pipeline with deterministic data, immutable manifests, quality checks and transactional publication. The repository includes a runnable offline reference and an AWS Glue → S3 → Snowflake cloud integration lab. Check the implementation-status guide for exactly what has been verified.”

Repository: https://github.com/datainteg/end-to-end-data-engineering-project

Pinned exercise: “Run the baseline, replay it, then remove one selected raw file. Does the committed watermark change? Compare your result with the automated tests.”

Only advertise a deployed AWS-to-Power-BI result after it has actually been demonstrated. Replace chapter estimates with measured timestamps before publishing. Thumbnail concept: presenter in a black shirt, a simplified source → pipeline → metrics flow, and the short headline **BUILD + TEST A PIPELINE**. A presenter image has not been supplied; no finished thumbnail is included.
