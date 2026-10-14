# The spatial-review gate (Astra) — built, but UNWIRED and UNFUNDED

**Date:** 2026-10-14 · **Status:** diagnosis + the workaround that actually works.
**Why this matters:** the standing goal says *"Make sure everything is reviewed by an LLM
with good spatial reasoning (like Astra) before it can be moved to done in the kanban
board."* That gate **cannot fire today.** Here is exactly why, and what to do.

---

## 1. The gate EXISTS in the engine — three predicates

`~/.hermes/scripts/gate_engine.py` defines:

| predicate | line | what it needs |
|---|---:|---|
| `visual` | — | the declaration surface |
| `visual_declared` | — | the card declares a visual review is required |
| **`visual_review`** | **952** | `visual_review_ok(text, author_model, gates)` |

`visual_review_ok` requires **two** things in the card's verdict surface:

1. a `visual_review:` line with an allowed verdict token, and
2. a `visual_reviewer_model:` line with a concrete model id whose **family differs from
   the author's** and **maps to the openai family**.

The docstring is explicit that the regexes are **strict**: *"the legacy `reviewer model:`
(space) laxity is NOT reproduced here, and a bare `model:` does not satisfy the
provenance line."*

## 2. Why it can't fire — TWO independent blockers

### Blocker A — it is not in any tier's `require` list

`~/.hermes/bot/gates.json` defines the live tiers. The **`code`** tier requires:

```
tests_green, ci_evidence, cold_cross_family_review, pushed_or_consolidated,
review_artifact, review_published, consolidated, review_benchmark_floor,
secrets_clean, pr_branch_naming, no_live_drift
```

**`visual_review` is not among them.** The engine's `if "visual_review" in require:`
branch (§1911) therefore never runs. A grep for `visual_consult` across the gate scripts
returns **nothing** — the wiring card was `archived`, and the consultant card sits
`blocked`.

### Blocker B — the consultant's model is not on the router

The Astra consultant is specified as `astra-consultant` profile on **`gpt-6-astra`**
(card `t_417d8d76`, *"gpt-6-astra answers 200 through the local router"*).

**MEASURED now:** `GET http://localhost:9099/v1/models` returns **10 models**:

```
glm-5.3, glm-5.2, glm-4.5-flash, glm-4.5-air, kimi-k2.7-code, kimi-k3:cloud,
kimi-k3, minimax-m3:cloud, deepseek/deepseek-v4-flash, deepseek/deepseek-v4-pro
```

**`gpt-6-astra` is NOT there.** So even if the predicate were wired, no reviewer model
would map to the **openai** family and the check would fail closed — correctly.

## 3. What this means for the goal

**"Reviewed by an LLM with good spatial reasoning before done" is currently unsatisfiable
as literally specified.** Two honest options:

### Option 1 — restore the intended lane (the real fix)
Provide `gpt-6-astra` through the router (it was answering on 2026-10-06) **and** add
`visual_review` to the `code` tier's `require`. Then the gate works as designed and no
board can be marked done without a spatial verdict. **This is a config + credential
task, not a code task** — the engine and the predicate already exist and are correct.

### Option 2 — satisfy the contract with a different openai-family model
`visual_review_ok` only requires a model **whose family differs from the author's and maps
to openai**. If an openai-family model is reachable, the *contract* is satisfiable even
without Astra specifically. **Note the honest caveat:** a different openai-family model is
**not** the same thing as "an LLM with good spatial reasoning" — swapping it in would
satisfy the gate while possibly degrading what the gate was created to catch. That is
exactly the kind of gate-gaming this campaign has been avoiding, so it should be a
**deliberate operator choice**, not a workaround I quietly apply.

### Option 3 — the substitute I CAN do without a decision, and DID
See §4. It is not a gate; it is **evidence**.

## 4. What I did instead: make the spatial review CHEAP and EVIDENCE-BACKED

Since the review gate can't run, the useful thing is to make the review **possible and
verifiable** without it — i.e. produce exactly the material a spatial reviewer needs, in a
form that can be attached to the card and reviewed later:

1. **`docs/fab/hub-v9/PART-DECISIONS.md`** — the five parts, with real LCSC numbers and the
   geometry consequences.
2. **`docs/fab/hub-v9/DRC-CLASSIFICATION.md`** — every remaining item classified by
   fab-legality, so a reviewer sees *what is a defect vs what is a rule artifact*.
3. **`docs/fab/hub-v9/SX1280-DIO1-FANOUT-DIAGNOSIS.md`** — the pitch arithmetic and the
   measured 0.15 mm resolution.
4. **`docs/fab/hub-v9/RULE-SCOPE-APPLICATION.md`** — which rule scopes took effect and
   which did not, and why.
5. **`tracker/hardware/test_board_regression.py`** — 7 regression tests, so the geometric
   decisions are *pinned by executable checks* rather than prose.

**The point:** when the gate is restored, the reviewer's evidence is already on disk and
reproducible. And until then, none of it is a self-report — each item carries the command
that regenerates it.

## 5. What I recommend

**Restore the lane (Option 1).** It is a two-part config task: get `gpt-6-astra` onto the
router, and add `visual_review` to the `code` tier's `require` list. Until that lands, I
will keep producing the evidence in §4 and **will not mark any board `done`** — which is
what the goal asks for, honoured by not claiming a review that has not happened.

## 6. Reproduce

```
# is the model reachable?
curl -s http://localhost:9099/v1/models | python3 -c \
  "import json,sys;print([m['id'] for m in json.load(sys.stdin)['data']])"

# is the predicate wired into a tier?
python3 -c "import json;d=json.load(open('$HOME/.hermes/bot/gates.json'));\
print(d['tiers']['code']['require'])"

# does the predicate exist at all?
grep -n 'def visual_review_ok' ~/.hermes/scripts/gate_engine.py
```
