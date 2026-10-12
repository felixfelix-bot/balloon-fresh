# Per-run reports

One file per harmonized bench run, named `<run-id>.md`:

```
<yymmddHHMM>-<txtag>-<rxtag>-<band>.md
e.g. 2608281430-e80-esp32-868.md
```

The run id is the `SESSION <id>` value the tool writes into the CSVs, so the
report name and the data are joinable by eye.

Write it from [`../HARMONIZED-RUN-REPORT-TEMPLATE.md`](../HARMONIZED-RUN-REPORT-TEMPLATE.md).
Commit the report **and** the four artifacts it cites
(`<prefix>-summary.csv`, `<prefix>-pkts.csv`, `<prefix>-report.md`,
`<prefix>-meta.json`) in the same commit.

Then add the run's rows to
[`../HARMONIZED-RESULTS.md`](../HARMONIZED-RESULTS.md) in the matching
board-pair × band table and update its §1 "Data status".

Directory is intentionally empty until the first cross-board run happens — see
"Harmonized Results" §1. Do not add a report for a run that did not occur.
