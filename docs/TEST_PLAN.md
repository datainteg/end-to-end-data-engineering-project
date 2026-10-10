# Acceptance and recording evidence

> Original target design. For the current runnable release, verification results and deliberate simplifications, read [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

All cases below are planned, not executed. Tests should exercise outcomes and failure boundaries rather than mirror implementation. Use the deterministic fixture in [DATA_CONTRACTS.md](DATA_CONTRACTS.md).

| Case | Action | Required result | Requirement |
| --- | --- | --- | --- |
| T01 Baseline | Extract/transform/publish all fixture data | Sales ₹1,200; paid orders 2; AOV ₹600; attempt success 50% | DE-01–10,16 |
| T02 Actual connectors | Read PostgreSQL JDBC and MongoDB from Glue | Both cloud jobs return expected records, types and manifests | DE-02–03 |
| T03 Incremental join | Update one line, leave its customer/product unchanged | Correct enrichment and complete affected order; no missing lookup | DE-05,07 |
| T04 Replay | Replay same published batch and overlap window | No extra facts or SCD versions; sums unchanged | DE-11–12 |
| T05 Customer history | Change C001 tier and process next batch | Old observed version closed, exactly one current new version; existing fact attribution stable | DE-11 |
| T06 Empty source delta | Completed manifest with zero rows/files | Valid batch; successful publication advances watermark | DE-05–06 |
| T07 Missing data | Remove a selected file or dataset from a test attempt | Validation failure; transform/publication not run; watermarks unchanged | DE-06 |
| T08 Bad row | Add negative quantity and malformed monetary value | Reason-coded quarantine; per-stage accounting balances | DE-07 |
| T09 Duplicate/conflict | Add duplicate keys and conflicting same-time records | Exact duplicates collapse; ambiguous conflicts stop publication | DE-07,10 |
| T10 Fan-out | Add two reviews and two payment attempts to one customer/order | Sales unchanged; reviews/payments remain at their own grains | DE-07,18 |
| T11 Rollback | Fail between dimension updates and watermark update | No partial target/control transaction visible | DE-12 |
| T12 Lost commit response | Simulate client timeout after SQL commit | Ledger reconciliation reports success; transaction not repeated | DE-12 |
| T13 Orchestrator propagation | Force failed/timed-out AWS execution | Airflow fails; error contains correlated IDs | DE-13–14 |
| T14 Duplicate start | Start same pipeline twice through different entry points | Only lease owner can publish; other start rejected/serialized | DE-12–14 |
| T15 Follow-up failure | Fail notification or BI refresh after publication | Published ledger and data stay valid; follow-up retry only | DE-15–16 |
| T16 Deletion | Soft-delete an order/line/customer | Model flags and metrics follow the documented policy; no physical-delete claim | DE-05,10 |
| T17 Schema drift | Remove required field; separately add optional field | Required change fails; optional change follows explicit schema policy | DE-06–08 |
| T18 Fresh setup | Follow release instructions in isolated environment | Same fixture outputs, no undocumented dependencies | DE-17,VID-02 |

Critical schema errors, broken keys, missing objects and reconciliation failures block publication. Quarantinable row rules must be explicitly enumerated; do not silently lower thresholds to make the demo green.

## Evidence record per test

Store case ID, timestamp, code release, dataset seed, environment/version matrix, expected result, actual result, pass/fail, execution/query IDs and sanitised screenshots/log references. Planned numbers are not measured results until the case passes.

For the video, record T01, T04, T05 and T07/recovery in full. Keep other acceptance evidence in the repository. Screen captures should show source/target queries and IDs, not only green orchestration boxes.

## Video quality gate

- Each chapter has a clear input → action → output sequence and the claimed result is visible.
- Code and metric definitions remain readable at normal playback scale; overlays do not obscure executed lines.
- Startup waits may be edited out with “wait shortened” labels; no speed or latency claim follows from the edit.
- Final audio/captions match the picture, including chapter boundaries and the ending.
- Probe and decode the delivered MP4; verify resolution, frame rate, runtime and audio presence.
- Recheck description links and chapter starts against the measured final export.
