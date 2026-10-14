# REPORT.md

Task: t_53b0268f — V9-DUAL-LR evaluation

Delivered `docs/V9-DUAL-LR-DESIGN-MEMO.md`, a short ADR-029 amendment/memo. It concludes that 868-uplink / 2.4-GHz-downlink is simultaneous only with two independent LR2021 transceivers, but rejects that population for v9: two 39.6 x 21.6 mm F33 modules cannot fit 55 x 45 mm, and the nested bare-module footprint is mutually exclusive rather than simultaneous. It records the harmonic arithmetic (2604 MHz / 2609.55 MHz), explicitly marks attenuation as unmeasured, requires a conducted filter/desense test, and gives +4 GPIO shared-bus or +7 GPIO separate-bus deltas plus +0.8/+0.9 A F33 peak-current deltas.

It also preserves the operator-ratified SX1280 decision and costs/mitigations: dedicated SPI/control/feed, three-way 2.4-GHz arbitration, TDM, BUSY polling, antenna separation and power/thermal testing.

Verification: `git diff --check` passed on the clean detached origin/main worktree. No firmware changed, so no firmware compile is applicable. The memo and report are currently uncommitted/unpushed because this task workspace was scratch and the source repo has unrelated dirty changes; next step is to import/commit this docs-only cluster on the balloon docs branch and push to origin and ngit.

Remaining:
1. Commit the memo + PROGRESS.md + REPORT.md on an isolated balloon-fresh docs branch/worktree.
2. Push the observed commit to origin and ngit.
3. Optionally attach/link the committed memo to the kanban card.
4. Obtain the required conducted harmonic/desense measurement before claiming an attenuation number.
