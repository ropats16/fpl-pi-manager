# Gaffer architecture — cross-track synthesis (input to the #9 grilling)

What the three research tracks + the #25 run study agree on, and the decisions they leave
open. Every claim links to a raw file; raws carry the primary URLs. 2026-08-18.

Raws: [agent-org-design](raw/agent-org-design.md) · [season-long-machinery](raw/season-long-machinery.md) ·
[reference-systems](raw/reference-systems.md). Constraints: map Decisions-so-far (#7 runtime, #8 LLM, #6 state).

## Converged findings (the evidence points one way)

1. **One head decides; many hands gather.** Multi-agent wins only on parallelizable,
   read-heavy evidence gathering (~15× tokens; 80% of the gain is token spend). One
   coherent team decision with coupled sub-choices is the single-continuous-context case.
   Debate meshes lose to one adversarial pass + self-consistency.
   ([agent-org-design §Q1](raw/agent-org-design.md)) — matches the #25 run's shape:
   5 evidence agents fed one synthesizing gaffer.
2. **Stepwise-across-the-day is the canonical blackboard regime, not a compromise.**
   Independent self-activating roles, one writer at a time, a monitor (the gaffer)
   choosing order, solution built incrementally via shared files (stigmergy). Cron wakes =
   scheduler ticks. ([agent-org-design §Q2](raw/agent-org-design.md)) — and the season-long
   cadence table gives the concrete schedule: daily price/news scans (usually no-op),
   weekly plan→finalise→review triad, monthly chip/calibration, on-event cup/price wakes
   ([season-long-machinery §5](raw/season-long-machinery.md)).
3. **Solver proposes, LLM disposes.** The ILP layer is commoditised (open solver, chips as
   MILP toggles, horizon 3–8 GW, decay 0.84–0.9, FT banking, MC over fixture scenarios);
   projections are the differentiator and even that moat is thin (free OpenFPL ≈ paid FPL
   Review; better on haulers). The only evidence-backed LLM role: judgment/tie-break/
   discipline over a quant core — minutes/rotation reading, chip-window commitment,
   break-vs-hold, risk posture, −4 acceptance. Never arithmetic, never projections.
   ([season-long-machinery §implications](raw/season-long-machinery.md),
   [reference-systems §Q3–Q5](raw/reference-systems.md))
4. **File conventions converged industry-wide:** small per-role persona file; per-task
   skills with name+description frontmatter, progressively disclosed (~100-token metadata
   until triggered); curated capped memory index (<200 lines / 20–60k chars); Karpathy
   raw/-immutable + wiki layers (already in force here). The gaffer's power to edit
   assistant roles = rewriting these files. ([agent-org-design §Q3](raw/agent-org-design.md))
5. **Prompt assembly: tiered, index-then-fetch, hard ceiling ~25k in.** Measured context
   rot (sub-50% at 32K on hard retrieval) says never drift toward K2.5's 256K; critical
   facts at prompt start/end; assert the size bound in the harness (#16 AC).
   ([agent-org-design §Q4](raw/agent-org-design.md))
6. **Cheap-worker + premium-judge is validated** (FrugalGPT/RouteLLM): K2.5 assistants,
   escalation for decisions — and the judge should be a **different model family** than the
   worker (self-preference bias), which lands the AM/gaffer decision wakes on GPT-5.4.
   Grounding stack for K2.5 workers: schema-forced JSON + citation duty + CoVe-style
   independent verification. ([agent-org-design §Q5](raw/agent-org-design.md))
7. **Learning loop = bias flags, not weight refits.** One season cannot support learned
   weights; keep near-equal bucket weights, log per-decision sensitivity, review monthly.
   ([season-long-machinery §4](raw/season-long-machinery.md))
8. **Benchmark: sustained top 100k (~2,150+ pts) beats every reference with a public
   record; hard sanity floor = beat optimal set-and-forget (~2,420–2,531); reach top 10k.**
   No reference system anywhere publishes a verifiable live rank — self-reported claims
   carry severe survivorship bias. ([reference-systems §Q2, §Q6](raw/reference-systems.md))
9. **Security constraint on the memory design:** K2-family models were ~95% memory-
   poisonable in a recent study; the LLM-owned wiki needs reviewed writes and quarantined
   external content (mechanisms → #10, but the file set/write paths are #9's).
   ([agent-org-design §Q3.5](raw/agent-org-design.md))

## What the #25 run adds (organizational evidence)

- Implicit scope rule that worked: **an assistant owns one signal axis + its data sources,
  produces one immutable report, and must NOT propose a squad** (4 of 5 drifted — tighten).
- **The adversary earns its seat**: AM caught the run's one real defect; the optimizer-audit
  agent falsified the gaffer's own premise. Roles with *different goals/checks* pay;
  parallel same-goal agents don't.
- **Cross-joining inputs is the gaffer's job and it failed once** (Diop): whoever is
  downstream of two reports must be charged with joining them.
- Merge axes sharing a source/method; zero-weight axes get no agent; tools get auditors,
  not votes; conflicts get a reconciliation table (2 went unlogged).

## Cost shape (rough, to be locked in the grilling)

Per #8: lean K2.5 wake ≈ $0.02; a 6-agent fan-out per wake ≈ $7–17/mo ❌. Stepwise shape:
daily no-op scans (~30 × $0.02 ≈ $0.6) + weekly triad with bounded fan-out (4 analyst
briefs × 4 GWs ≈ $0.3 K2.5) + gaffer synthesis & AM on GPT-5.4 weekly (~$1–1.5) + monthly
chip/calibration (~$0.2) ≈ **$2–2.5/mo** — inside the $5 ceiling with headroom for
deadline-day escalations. Numbers are estimates; #9's decision doc must pin them.

## Open decisions the grilling must resolve

1. **Roster**: assistants map to the 5 signal buckets, or fewer merged roles, or
   cadence-based roles (daily scout / weekly analysts)? Scout: standing sub-agent or
   gaffer behavior?
2. **Which wakes fan out** (weekly plan-refresh only?) vs single-agent wakes; final cost
   table.
3. **Model map**: which calls run K2.5 vs GPT-5.4 (workers cheap; AM + squad-lock premium?).
4. **File set + naming**: persona/role files, skills, memory index, workspace layout
   (avoid AGENTS.md collision per #31); who may write what; role-edit protocol
   (gaffer edits assistant files — with or without Rohit approval?).
5. **Prompt assembly policy**: always-in set vs fetch-on-demand; the numeric size bound.
6. **AM charter**: scope (draft challenge only vs also memory-write review), cadence, model.
7. **Judgment authority**: free-hand per-decision weighting vs bounded, logged override
   (research favors bounded; #25 practiced free-with-logging).
