# Agent-Organization Design Patterns — raw research (Track A of 3, issue #9)

> **Scope.** Primary-source evidence on how to organize a small autonomous LLM decision
> daemon (the FPL "gaffer"): single-vs-multi agent, time-sliced/blackboard scheduling,
> persona/workspace file conventions, bounded-prompt assembly, and cheap-worker/premium-judge QC.
> Produced by Claude Opus 4.8 orchestrating 5 parallel Opus-4.8 leaf researchers; every
> load-bearing number below was re-fetched from its primary page by the orchestrator.
>
> **Evidence tiers** (per repo convention): **[proven]** = measured & replicated / peer-reviewed
> controlled result · **[standard]** = widely-accepted documented practice · **[tier-1]** = single
> credible primary source (vendor eng-blog, arxiv preprint, official docs) · **[tier-2/folklore]** =
> practitioner blog opinion / anecdote / secondary reporting · **[unverified]** = could not confirm
> on a primary page — do NOT rely on.
>
> **Design target recap.** ~500-line DIY Python daemon on a Pi 4B (≈1.8GiB usable RAM; compute/RAM
> is the constraint, storage is not). LLM calls → OpenRouter: Kimi K2.5 default ($0.60/$3.00 per 1M),
> GPT-5.4 escalation ($2.50/$15.00), ~$5/mo budget, lean wake ≈ 25k in / 2k out. Cron 1–3×/day +
> Telegram wake-on-message. All agent knowledge is markdown/JSON in a git repo (Karpathy LLM-wiki
> convention). Human (Rohit) = observer + approval gate. Owner's direction: assistants need NOT run
> simultaneously — stepwise across the day, each reporting back; the gaffer holds supreme decision
> power (team selection AND editing assistant roles); an assistant-manager role pushes back on the
> gaffer's draft before finalization.

---

## Q1 — Orchestrator-worker vs debate/adversarial vs single-agent-with-lenses: when does multi-agent actually beat single?

### 1.1 Anthropic multi-agent research system — the headline gain AND its cost **[tier-1]**

Anthropic reports a large measured gain from a lead+subagent architecture:

> "a multi-agent system with Claude Opus 4 as the lead agent and Claude Sonnet 4 subagents
> outperformed single-agent Claude Opus 4 by 90.2% on our internal research eval."

— https://www.anthropic.com/engineering/multi-agent-research-system (orchestrator re-fetched; verbatim)

**But the same post is candid that the gain largely tracks token spend, not architecture magic** —
the strongest adversarial point sits *inside* the pro-multi-agent source:

> "agents typically use about 4× more tokens than chat interactions, and multi-agent systems use
> about 15× more tokens than chats."

> "token usage by itself explains 80% of the variance [in the eval], with the number of tool calls
> and the model choice as the two other explanatory factors."

And Anthropic explicitly *scopes* the benefit to parallelizable, read-heavy, high-value work:

> "Multi-agent systems excel at valuable tasks that involve heavy parallelization, information that
> exceeds single context windows, and interfacing with numerous complex tools."

> "multi-agent research systems excel especially for breadth-first queries that involve pursuing
> multiple independent directions simultaneously."

> "For economic viability, multi-agent systems require tasks where the value of the task is high
> enough to pay for the increased performance."

**Tier:** [tier-1] — first-party, single, *private/non-replicated* eval on a task (research/browsing)
that is inherently breadth-first and read-heavy; favorable to parallelism. The 80%-variance-from-tokens
line is the load-bearing caveat: a single agent given the same token budget is not isolated as a control.

### 1.2 Cognition "Don't Build Multi-Agents" — the opposing practitioner view **[tier-2/folklore]**

Cognition (builders of Devin, a *coding* agent) argues the opposite for tightly-coupled work:

> Principle 1: "Share context, and share full agent traces, not just individual messages"
> Principle 2: "Actions carry implicit decisions, and conflicting decisions carry bad results"

> "Subagent 1 and subagent 2 cannot not see what the other was doing and so their work ends up being
> inconsistent with each other." *(sic — double negative in original)*

> "The simplest way to follow the principles is to just use a single-threaded linear agent … Here,
> the context is continuous."

— https://cognition.ai/blog/dont-build-multi-agents (→ https://cognition.com/blog/dont-build-multi-agents)

**Tier:** [tier-2/folklore] — reasoned practitioner opinion, no benchmark numbers. The Anthropic↔Cognition
disagreement is *task-shaped*: read-heavy/decomposable research (Anthropic) favors fan-out; write-heavy
work producing one coherent artifact with interdependent sub-decisions (Cognition's coding) favors a
single continuous context.

### 1.3 Multi-agent debate DOES measurably improve reasoning/factuality **[proven]**

Du et al., "Improving Factuality and Reasoning in Language Models through Multiagent Debate" (ICML 2024):

> "This approach significantly enhances mathematical and strategic reasoning across a number of tasks."
> "…improves the factual validity of generated content, reducing fallacious answers and hallucinations
> that contemporary models are prone to."

Measured (single agent → 3-agent/2-round debate): Arithmetic 67.0%→81.8%; GSM8K 77.0%→85.0%; Biography
factuality 66.0%→73.8%; Chess move quality (Δ pawn) 91.4→122.9.
— https://arxiv.org/abs/2305.14325 · numbers via https://arxiv.org/html/2305.14325v1
**Tier:** [proven] (peer-reviewed, measured). Caveat: gains consume extra compute (agents × rounds); the
paper does not use a **cost-matched single-agent-with-sampling** baseline.

### 1.4 …but debate does NOT reliably beat cheaper self-consistency/sampling **[proven]**

The adversarial counter — the cheap baseline any multi-agent design must beat:

Smit et al., "Should we be going MAD? A Look at Multi-Agent Debate Strategies for LLMs" (ICML 2024):
> "multi-agent debating systems, in their current form, do not reliably outperform other proposed
> prompting strategies, such as self-consistency and ensembling."
— https://arxiv.org/abs/2311.17371 · https://proceedings.mlr.press/v235/smit24a.html

Li et al., "More Agents Is All You Need":
> "simply via a sampling-and-voting method, the performance of large language models (LLMs) scales
> with the number of agents instantiated."
— https://arxiv.org/abs/2402.05120 · (claimed "Llama2-13B @ 15 agents ≈ Llama2-70B" surfaced but
**[unverified]** against the PDF body)
**Tier:** [proven] for the sampling-scaling and MAD-not-superior claims. Bottom line: **embarrassingly-parallel
sampling+voting on ONE model captures much of the "multi-agent" benefit at a fraction of orchestration cost.**

### 1.5 Q1 synthesis

The axis that decides single-vs-multi is **task decomposability**, not head-count. Read-heavy / breadth-first
/ independent-subtask work → orchestrator-worker (or plain parallel sampling) pays off, at ~15× tokens.
Tightly-coupled work yielding one coherent decision with interdependent sub-choices → single continuous-context
agent is more reliable. **Debate/adversarial review buys measured factuality/calibration gains, but the honest
cheap baseline is single-agent + self-consistency sampling.** For a ~$5/mo daemon, 15× token blow-up is
disqualifying unless the parallel work is genuinely independent and read-heavy.

---

## Q2 — Time-sliced / staggered "same model, different persona, shared file" scheduling: blackboard & stigmergy

### 2.1 Blackboard classic: independent knowledge sources, shared store, NO direct KS-to-KS comms **[proven]**

Hearsay-II (Erman, Hayes-Roth, Lesser, Reddy — *ACM Computing Surveys* 12(2), 1980):
> "Because each KS is an independent condition-action module, KSs communicate through a global database
> called the blackboard."
> "the implicit data-directed approach was taken, in which KSs interact uniformly and anonymously via
> the blackboard."
— https://mas.cs.umass.edu/Documents/Erman_Hearsay80.pdf · DOI https://dl.acm.org/doi/10.1145/356810.356816

Nii, "Blackboard Systems" (*AI Magazine*, 1986):
> "There is a global database called the blackboard, and there are logically independent sources of
> knowledge called the knowledge sources. The knowledge sources respond to changes on the blackboard.
> Note that there is no control flow; the knowledge sources are self-activating."
— http://i.stanford.edu/pub/cstr/reports/cs/tr/86/1123/CS-TR-86-1123.pdf · DOI https://onlinelibrary.wiley.com/doi/abs/10.1609/aimag.v7i2.537
**Tier:** [proven]/[tier-1] (peer-reviewed primary; verbatim-confirmed by leaf agent from the PDFs).

### 2.2 The classic model is explicitly OPPORTUNISTIC, ONE-WRITER-AT-A-TIME, STAGGERED — directly supports the owner's stepwise shape **[proven]**

Hearsay-II:
> "We refer to such an ability of a system to exploit its best data and most promising methods as
> opportunistic problem solving."
> "a heuristic scheduler … calculates a priority for each action and executes, at each time, the
> waiting action with the highest priority."

Nii's jigsaw analogy (the clearest statement of the stepwise/staggered shape):
> "The whole puzzle can be solved in complete silence: that is, there need be no direct communication
> among the group. Each person is self-activating … No a priori established order exists…"
> "the solution is built incrementally (one piece at a time) and opportunistically (as an opportunity
> for adding a piece arises)"
> "no more than one person can go up to the blackboard at one time, and a monitor is needed, someone
> who can see the group and can choose the order in which a person is to go up to the blackboard."

**Tier:** [proven]/[tier-1]. **This is direct classical support for the owner's design:** independent,
self-activating roles; one writer at a time; a scheduler/monitor picking order dynamically; solution built
incrementally across time — i.e. *stepwise, not simultaneous*. The gaffer is Nii's "monitor."

### 2.3 Stigmergy: coordination via traces left in a shared medium, "by the same or other agents" **[tier-1]**

Heylighen, "Stigmergy as a Universal Coordination Mechanism" (*Cognitive Systems Research*, 2016; concept
coined by Grassé 1959):
> "work performed by an agent leaves a trace in the environment that stimulates the performance of
> subsequent work—by the same or other agents."
> "This mediation via the environment ensures that tasks are executed in the right order, without any
> need for planning, control, or direct interaction between the agents."
— https://pespmc1.vub.ac.be/Papers/Stigmergy-varieties.pdf
**Tier:** [tier-1] (peer-reviewed; canonical definition). **Relevance:** the exact framing for same-substrate
coordination where the "trace" is a shared markdown/state file and the "next action" is a later same-model
invocation reading that trace — explicitly *by the same or other agents*, with *no direct agent-to-agent* comms.

### 2.4 Modern LLM revivals of the blackboard/shared-file pattern **[tier-2]**

- Han & Zhang, "Exploring Advanced LLM Multi-Agent Systems Based on Blackboard Architecture" (arXiv:2507.01701):
  agents "share all the information … during the whole problem-solving process," "agents that will take
  actions are selected based on the current content of the blackboard," repeated "until a consensus is
  reached." — https://arxiv.org/abs/2507.01701
- Salemi et al. (Google), "LLM-based Multi-Agent Blackboard System for Information Discovery in Data Science"
  (arXiv:2510.01285): "A central agent posts requests to a shared blackboard, and autonomous subordinate
  agents … volunteer to respond based on their capabilities." — https://arxiv.org/html/2510.01285v1
**Tier:** [tier-2] (arxiv preprints, primary but not peer-reviewed). Framework analogs (AutoGen/AG2 group-chat
shared log; LangGraph shared-state) are widely cited but **[unverified]** here (official docs not fetched this pass).

### 2.5 Q2 synthesis

The owner's "stepwise-across-the-day, each reports back, gaffer decides" shape is **not a workaround — it is the
canonical blackboard control regime** (opportunistic, one-writer-at-a-time, scheduler-ordered) plus stigmergic
coordination through shared files. Classic literature (40+ years, [proven]) endorses it directly, and it's being
revived for LLM agents ([tier-2]). This is the best-supported organizational pattern for the gaffer.

---

## Q3 — Persona / workspace / skills file conventions, and their documented failure modes

### 3.1 Claude Code / Anthropic conventions **[proven]**

**Agent Skills = `SKILL.md` + YAML frontmatter + progressive disclosure.** Required frontmatter fields are
`name` and `description` (orchestrator re-fetched the docs page verbatim):
> "**Required fields:** `name` and `description`" — `name` "Maximum 64 characters … only lowercase letters,
> numbers, and hyphens … Cannot contain reserved words: 'anthropic', 'claude'"; `description` "Maximum 1024
> characters … must include both what the Skill does and when Claude should use it."

Three-level progressive disclosure with a token table: **Level 1 metadata "~100 tokens per Skill" (always
loaded)** → **Level 2 SKILL.md body "Under 5k tokens" (loaded when triggered)** → **Level 3 resources/scripts
"None until accessed."** — https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
Eng-blog: "a skill is a directory that contains a `SKILL.md` file … Progressive disclosure is the core design
principle" — https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills

**Subagents = `.md` file with frontmatter (`name`, `description`, `tools`, `model`); body becomes the system
prompt.** `model` "Defaults to `inherit`"; `tools` "Inherits every tool available to subagents if omitted."
Live in `.claude/agents/` (project) or `~/.claude/agents/` (user). — https://code.claude.com/docs/en/sub-agents

**CLAUDE.md memory + `MEMORY.md` index.** Four scopes load broad→specific; `@path` imports up to 4 hops; auto-memory
loads "The first 200 lines of `MEMORY.md`, or the first 25KB, whichever comes first … at the start of every
conversation"; guidance: "target under 200 lines per CLAUDE.md file. Longer files consume more context and reduce
adherence." — https://code.claude.com/docs/en/memory
**Tier:** [proven] (official docs, verbatim).

### 3.2 AGENTS.md open convention **[proven]**

> "Think of AGENTS.md as a README for agents … A simple, open format for guiding coding agents, used by over
> 60k open-source projects." "AGENTS.md is just standard Markdown." — https://agents.md/
Claude Code reads CLAUDE.md (not AGENTS.md) but supports `@AGENTS.md` import/symlink to bridge.
**Tier:** [proven] for the spec/site. Governance history (OpenAI+Google Aug-2025 formalization; Linux-Foundation
donation) is [tier-2/folklore], secondary reporting — https://www.infoq.com/news/2025/08/agents-md/

### 3.3 Karpathy "LLM Wiki" markdown-knowledge convention **[tier-1 artifact / unverified tweet]**

Pattern: an LLM incrementally builds & maintains a persistent interlinked Markdown knowledge base instead of
re-retrieving raw chunks per query. Primary artifact = public gist under the `karpathy` account:
> "Instead of just retrieving from raw documents at query time, the LLM incrementally builds and maintains a
> persistent wiki" — https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
**Tier:** [tier-1] for the gist. The oft-cited accompanying *tweet* and the "raw/ immutable + generated wiki +
schema" three-layer structure are **[unverified]/[tier-2]** (secondary write-ups, not confirmed on the gist body).
*(This repo already follows the raw/-immutable convention — cf. `plans/research/team-selection/`.)*

### 3.4 OpenClaw / PicoClaw-style daemons: SOUL.md, MEMORY.md, IDENTITY.md **[proven for OpenClaw / unverified for PicoClaw]**

OpenClaw injects a workspace of markdown files into the system prompt each session (orchestrator re-fetched
docs verbatim): **AGENTS.md** "Operating instructions … and how it should use memory"; **SOUL.md** "Persona,
tone, and boundaries"; **IDENTITY.md** "The agent's name, vibe, and emoji"; **USER.md** "Stable preferences …
active-project context" (optional); **MEMORY.md** "Curated long-term memory: durable non-profile facts,
decisions, and short summaries" (optional). Bootstrap truncation budgets: `bootstrapMaxChars` **20,000**,
`bootstrapTotalMaxChars` **60,000**, USER.md cap **4,000** chars; plus daily logs `memory/YYYY-MM-DD.md`.
— https://docs.openclaw.ai/concepts/agent-workspace
**Tier:** [proven] for OpenClaw. **PicoClaw/NanoClaw-specific** SOUL.md/MEMORY.md conventions and OpenClaw
`HEARTBEAT.md` are **[unverified]** — no primary repo/README located; referenced only in secondary text.

### 3.5 Documented failure modes

**(a) Memory / context poisoning — persistent memory is a long-lived attack surface [tier-1].**
"Hidden in Memory: Sleeper Memory Poisoning in LLM Agents" (arXiv:2605.15338) — orchestrator re-fetched the
abstract to confirm this suspicious-looking claim is real:
> "an adversary manipulates external context … to cause the assistant to store a fabricated memory about the user."
> "Poisoned memories were added up to 99.8% on GPT-5.5 and 95% on Kimi-K2.6."
> "poisoned memories cause attacker-intended agentic actions in 60–89% of evaluations across models."
> "Persistent memory can act as a long-term attack surface across multiple future conversations."
— https://arxiv.org/abs/2605.15338. **Directly relevant: Kimi-K2.6 (same family as the gaffer's K2.5 default)
was 95% poison-able.** Claude Code's own memory doc surfaces a trust dialog for externally-committed files for
this reason. (Cisco-compromised-Claude-Code-memory reporting is [tier-2/folklore]: https://www.darkreading.com/vulnerabilities-threats/bad-memories-haunt-ai-agents)

**(b) SKILL.md / instructions as prompt-injection & code-execution vector [proven].** Official Skills docs,
verbatim (orchestrator-confirmed):
> "a malicious Skill can direct Claude to invoke tools or execute code in ways that don't match the Skill's
> stated purpose."
> "**External sources are risky:** Skills that fetch data from external URLs pose particular risk, as fetched
> content may contain malicious instructions." "**Treat like installing software**."
— https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview

**(c) Context bloat / context rot [tier-1].** (Detailed measured evidence in Q4.) Anthropic: "as the number of
tokens in the context window increases, the model's ability to accurately recall information from that context
decreases"; models have an "attention budget … Every new token introduced depletes this budget." Operationalized
by Claude Code's "under 200 lines per CLAUDE.md" guidance.

### 3.6 Q3 synthesis

Converging convention across Claude Code, AGENTS.md, Karpathy-wiki, and OpenClaw: **per-role identity in a small
markdown file (persona/boundaries), per-task capability in progressively-disclosed skill files (metadata always
loaded, body on trigger), shared memory in a curated + capped index file.** Failure modes to design against:
(a) poisoned memory — treat any auto-written memory + externally-sourced facts as untrusted, esp. on the K2 family;
(b) skill/instruction injection — only load trusted, audited skills, quarantine external-fetch content;
(c) context bloat — hard line/char caps per file (OpenClaw 20k/60k chars; Claude Code <200 lines).

---

## Q4 — Prompt assembly under a token ceiling; tiered memory; context-rot evidence

### 4.1 MemGPT / Letta — tiered "virtual context" (paging between main + external context) **[tier-1]**

Packer et al., "MemGPT: Towards LLMs as Operating Systems" (arXiv:2310.08560):
> "we propose virtual context management, a technique drawing inspiration from hierarchical memory systems in
> traditional operating systems that provide the appearance of large memory resources through data movement
> between fast and slow memory."
> "MemGPT … intelligently manages different memory tiers in order to effectively provide extended context within
> the LLM's limited context window."
Architecture: bounded **main context** (in-window) vs unbounded **external context** (out-of-window), with the
LLM issuing function calls to page/self-edit. — https://arxiv.org/abs/2310.08560
**Tier:** [tier-1] (foundational, widely-cited). This is the canonical tiered-memory primary source.

### 4.2 Index-then-fetch / "just-in-time" retrieval (pointers + summaries) **[tier-1]**

Anthropic, "Effective context engineering for AI agents":
> "agents built with the 'just in time' approach maintain lightweight identifiers (file paths, stored queries,
> web links, etc.) and use these references to dynamically load data into context at runtime using tools."
> "we generally don't memorize entire corpuses of information, but rather introduce external organization and
> indexing systems like file systems, inboxes, and bookmarks to retrieve relevant information on demand."
— https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
**Tier:** [tier-1] (official eng-blog). Maps cleanly onto a git-repo file workspace: keep an index + pointers in
the wake prompt, fetch full files only when needed.

### 4.3 Lean beats stuffed — "attention budget," diminishing returns **[tier-1]**

Same Anthropic post:
> "good context engineering means finding the smallest possible set of high-signal tokens that maximize the
> likelihood of some desired outcome."
> "Context … must be treated as a finite resource with diminishing marginal returns."
> "LLMs have an 'attention budget' … Every new token introduced depletes this budget by some amount."
> "as the number of tokens in the context window increases, the model's ability to accurately recall information
> from that context decreases."
**Tier:** [tier-1].

### 4.4 MEASURED long-context degradation ("context rot")

- **Lost in the Middle** (Liu et al., arXiv:2307.03172) **[proven]**:
  > "performance is often highest when relevant information occurs at the beginning or end of the input context,
  > and significantly degrades when models must access relevant information in the middle of long contexts, even
  > for explicitly long-context models." — https://arxiv.org/abs/2307.03172
- **Chroma "Context Rot"** (Hong, Troynikov, Huber; 18 models incl. GPT-4.1/Claude 4/Gemini 2.5/Qwen3) **[tier-1]**:
  > "their performance grows increasingly unreliable as input length grows."
  > "Even a single distractor reduces performance relative to the baseline (needle only), and adding four
  > distractors compounds this degradation further." — https://www.trychroma.com/research/context-rot
- **NoLiMa** (arXiv:2502.05167) **[proven, numbers lightly-verified]**: with lexical shortcuts removed, of 12
  models claiming ≥128K support, at 32K tokens ~10 drop below 50% of short-context baseline; GPT-4o 99.3%→69.7%.
  *(exact figures from abstract summary, not full-PDF — treat as [proven]-trend / [tier-1]-number.)*
  — https://arxiv.org/abs/2502.05167

### 4.5 Kimi K2.5 context window + Kimi-specific degradation **[tier-1 window / unverified degradation]**

Kimi K2.5 advertised context = **256K** (HuggingFace model card, orchestrator-confirmed: "Context Length … 256K";
1T total / 32B active params) — https://huggingface.co/moonshotai/Kimi-K2.5 — equivalently **262,144 ("262K")** on
the OpenRouter routing page the project uses — https://openrouter.ai/moonshotai/kimi-k2.5. **No published
Kimi-specific long-context degradation curve exists** (Chroma/NoLiMa/Lost-in-the-Middle don't test Kimi; the K2.5
card reports only aggregate LongBench-v2 61.0 / AA-LCR 70.0). Treat K2.5's usable context as **[unverified]** and
assume the general context-rot findings apply — especially since a mid-tier MoE default is likelier to degrade
than the frontier models Chroma tested.
**Tier:** [tier-1] window; [unverified] Kimi-specific degradation.

### 4.6 Q4 synthesis

Advertised context (256K/262K for K2.5) ≠ usable context. Every measured source ([proven] Lost-in-the-Middle
U-curve, [tier-1] Chroma non-uniform decline, [proven] NoLiMa sub-50% at 32K) plus Anthropic's finite-attention
guidance argues for a **MemGPT-style tiered design under a conservative ceiling**: small curated main-context wake
prompt (the ~25k-in budget is already the right instinct — keep it there, don't grow it toward 256K), file
workspace as external context, **index-then-fetch** (pointers + short summaries) rather than stuffing, and put the
single most decision-critical facts at the **start or end** of the prompt (avoid the lossy middle).

---

## Q5 — Quality control for cheap-model workers; cheap-worker + premium-judge hierarchies

### 5.1 FrugalGPT — LLM cascade (cheap-first, escalate on low confidence) **[tier-1]**

Chen, Zaharia, Zou (arXiv:2305.05176), abstract (orchestrator-confirmed verbatim):
> "FrugalGPT can match the performance of the best individual LLM (e.g. GPT-4) with up to 98% cost reduction or
> improve the accuracy over GPT-4 by 4% with the same cost." — https://arxiv.org/abs/2305.05176
**Tier:** [tier-1]. Caveat: "up to 98%" is best-case on 3 specific datasets (HEADLINES/OVERRULING/COQA), not
universal — calibrate the escalation threshold on the gaffer's own task.

### 5.2 RouteLLM — trained cheap/strong router **[tier-1]**

Ong et al. (LMSYS, arXiv:2406.18665 + blog):
> "cost reductions of over 85% on MT Bench, 45% on MMLU, and 35% on GSM8K" while targeting "95% GPT-4 performance."
> "the number of GPT-4 calls required to achieve 95% GPT-4 performance further halved at 14% of total calls."
— https://www.lmsys.org/blog/2024-07-01-routellm/ · https://arxiv.org/abs/2406.18665
**Tier:** [tier-1]. Confirms cheap-then-escalate empirically; savings are benchmark-dependent.

### 5.3 Schema-forced / structured outputs — makes cheap output machine-reliable **[tier-1]**

OpenAI Structured Outputs. Official docs (orchestrator-confirmed verbatim):
> "Structured Outputs is a feature that ensures the model will always generate responses that adhere to your
> supplied JSON Schema." — https://developers.openai.com/api/docs/guides/structured-outputs
Launch blog reports 100% schema-following (gpt-4o) vs <40% (gpt-4-0613) — https://openai.com/index/introducing-structured-outputs-in-the-api/
*(blog page 403'd to automated fetch; the ≥/<% eval figures are [tier-1] from the launch announcement, flagged.)*
**Key caveat:** schema forcing guarantees valid *shape/format*, **NOT semantic correctness** — it is machine-reliability, not grounding.
**Tier:** [tier-1].

### 5.4 LLM-as-judge / adjudicator — viable but biased **[tier-1]**

Zheng et al., "Judging LLM-as-a-Judge" (NeurIPS 2023, MT-Bench/Chatbot Arena):
> "strong LLM judges like GPT-4 can match both controlled and crowdsourced human preferences well, achieving over
> 80% agreement, the same level of agreement between humans."
Documented biases: "position, verbosity, and self-enhancement biases, as well as limited reasoning ability."
— https://arxiv.org/abs/2306.05685
**Tier:** [tier-1]. For a cheap-worker + premium-judge design: the judge is not neutral — de-bias by randomizing
answer order (position bias), controlling for length (verbosity bias), and **using a different model family as
judge than as worker** (self-enhancement bias). The assistant-manager "push-back" role IS an LLM-judge; apply these.

### 5.5 Self-verification (Chain-of-Verification) — cheap grounding layer **[tier-1]**

Dhuliawala et al. (Meta, arXiv:2309.11495):
> the model "(i) drafts an initial response; then (ii) plans verification questions to fact-check its draft;
> (iii) answers those questions independently so the answers are not biased by other responses; and (iv) generates
> its final verified response."
> "CoVe decreases hallucinations across a variety of tasks." — https://arxiv.org/abs/2309.11495
**Tier:** [tier-1]. The load-bearing design insight is step (iii): answering verification questions *independently*
(without seeing the draft) is what stops the model repeating its own errors — a citation/verify pattern runnable
on the cheap worker itself, no premium model required.

### 5.6 Q5 synthesis

Cheap-first-escalate is empirically validated ([tier-1] FrugalGPT ≤98% cost cut; RouteLLM 95% GPT-4 quality at
14% strong-model calls) — **directly endorses Kimi-K2.5-default + GPT-5.4-escalation.** Grounding stack for the
cheap worker: **(1) schema-forced outputs** for machine-reliable shape (≠ correctness), **(2) citation/verify
requirement** (CoVe-style independent self-check), **(3) a premium/different-family judge** for adjudication (the
assistant-manager push-back), de-biased for position/verbosity/self-preference. Escalate to GPT-5.4 only on
low-confidence / high-stakes decisions (transfers, chips) — not routine wakes.

---

## Implications for the gaffer (design mapping)

**Single-vs-multi → single gaffer + stepwise "lenses/roles," NOT simultaneous swarm.**
[proven] evidence says multi-agent's 90.2%-style wins come with ~15× tokens and mostly track token spend (Q1.1),
and only pay off on *parallelizable, read-heavy* work; the gaffer's core act — one coherent team-selection decision
with tightly-coupled sub-choices — is exactly the *write-heavy/coupled* case where a single continuous-context
agent is more reliable (Cognition, Q1.2). A ~$5/mo budget cannot afford 15×. **→ One supreme gaffer holds the
decision; "assistants" are the same model invoked with different persona/context at different times, each writing
back a bounded report.** Where you want a factuality/calibration bump, use the cheapest form that works: single-agent
self-consistency sampling or one adversarial push-back pass (assistant-manager), not a debate mesh (Q1.3–1.4).

**Stepwise scheduling → this is the canonical BLACKBOARD control regime; adopt it wholesale.** [proven] Hearsay-II /
Nii endorse independent, self-activating roles; **one writer at a time**; a **scheduler/monitor** (= the gaffer)
choosing order dynamically; solution built **incrementally, opportunistically, across time** (Q2.2). [tier-1]
stigmergy gives the file-as-trace framing "by the same or other agents … no direct interaction" (Q2.3). The owner's
"assistants run stepwise across the day, each reports back, gaffer decides" is textbook, not a compromise. Cron
wakes = scheduler ticks; each role reads current shared files, appends its trace, exits.

**File conventions → per-role identity file + progressively-disclosed skills + curated/capped shared memory.**
Follow the [proven] converged convention (Q3): small persona file per role (OpenClaw SOUL.md-style: persona, tone,
boundaries), per-task skills with `name`+`description` frontmatter loaded on trigger (~100 tokens metadata until
used), and a curated `MEMORY.md`-style index (Claude Code caps loading at 200 lines/25KB; OpenClaw at 20k/60k chars —
**impose hard caps**). The repo already uses the Karpathy raw/-immutable + wiki convention ([tier-1] gist). Gaffer's
"editing assistant roles" power = the gaffer rewriting these role/skill markdown files — well-supported.

**Prompt assembly → tiered, index-then-fetch, lean, under a hard ceiling.** [tier-1] MemGPT tiered memory + Anthropic
just-in-time retrieval + [proven] context-rot evidence (Q4). Keep the ~25k-in wake prompt *small and curated* — do
NOT drift toward K2.5's 256K window; measured degradation (Lost-in-the-Middle U-curve, Chroma, NoLiMa sub-50%@32K)
plus no Kimi-specific safety data means treat usable context as far below advertised. Wake prompt = small index +
pointers + short summaries; fetch full files only when a decision needs them; put the 1–2 most decision-critical
facts at prompt start/end, never buried mid-context.

**Cheap/premium split → Kimi-K2.5 worker + GPT-5.4 judge/escalation, with a grounding stack.** [tier-1] FrugalGPT /
RouteLLM validate cheap-default + escalate-on-low-confidence (Q5). Ground the K2.5 worker with: schema-forced JSON
(machine-reliable shape, not correctness), a citation/verify (CoVe-style independent self-check) requirement, and an
adjudicator. Make the **assistant-manager push-back an LLM-judge** — and de-bias it (randomize option order; control
verbosity; **judge with a different family, i.e. GPT-5.4, than the K2.5 worker** to avoid self-preference bias, Q5.4).
Reserve GPT-5.4 for low-confidence/high-stakes calls only. **Security caveat:** [tier-1] memory-poisoning showed
Kimi-K2.6 (same family) 95% poison-able — treat auto-written memory + external facts as untrusted, cap/curate them,
and quarantine any external-fetch content from the instruction stream (Q3.5).

---

## Sources

**Q1 — single vs multi**
- Anthropic, How we built our multi-agent research system — https://www.anthropic.com/engineering/multi-agent-research-system *(90.2% gain; 4×/15× tokens; 80% variance; breadth-first scope — orchestrator-verified)*
- Cognition, Don't Build Multi-Agents — https://cognition.ai/blog/dont-build-multi-agents
- Du et al., Multiagent Debate (ICML 2024) — https://arxiv.org/abs/2305.14325 · https://arxiv.org/html/2305.14325v1
- Smit et al., Should we be going MAD? (ICML 2024) — https://arxiv.org/abs/2311.17371 · https://proceedings.mlr.press/v235/smit24a.html
- Li et al., More Agents Is All You Need — https://arxiv.org/abs/2402.05120 *(13B≈70B@15 [unverified])*

**Q2 — blackboard / stigmergy**
- Erman/Hayes-Roth/Lesser/Reddy, Hearsay-II (ACM Comp. Surveys 1980) — https://mas.cs.umass.edu/Documents/Erman_Hearsay80.pdf · https://dl.acm.org/doi/10.1145/356810.356816
- Nii, Blackboard Systems (AI Magazine 1986) — http://i.stanford.edu/pub/cstr/reports/cs/tr/86/1123/CS-TR-86-1123.pdf · https://onlinelibrary.wiley.com/doi/abs/10.1609/aimag.v7i2.537
- Heylighen, Stigmergy as a Universal Coordination Mechanism (2016) — https://pespmc1.vub.ac.be/Papers/Stigmergy-varieties.pdf
- Han & Zhang, LLM MAS Based on Blackboard Architecture — https://arxiv.org/abs/2507.01701
- Salemi et al. (Google), LLM Multi-Agent Blackboard System — https://arxiv.org/html/2510.01285v1

**Q3 — file conventions / failure modes**
- Agent Skills overview — https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview *(orchestrator-verified frontmatter + security quote)*
- Anthropic, Equipping agents with Agent Skills — https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Subagents — https://code.claude.com/docs/en/sub-agents
- Memory / CLAUDE.md — https://code.claude.com/docs/en/memory
- AGENTS.md — https://agents.md/ · governance [tier-2] https://www.infoq.com/news/2025/08/agents-md/
- Karpathy LLM Wiki gist — https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- OpenClaw agent workspace — https://docs.openclaw.ai/concepts/agent-workspace *(orchestrator-verified files + char budgets)*
- Hidden in Memory: Sleeper Memory Poisoning in LLM Agents — https://arxiv.org/abs/2605.15338 *(orchestrator-verified; 99.8% GPT-5.5 / 95% Kimi-K2.6)*
- (secondary [tier-2]) DarkReading, Bad Memories Haunt AI Agents — https://www.darkreading.com/vulnerabilities-threats/bad-memories-haunt-ai-agents

**Q4 — prompt assembly / context rot**
- Packer et al., MemGPT — https://arxiv.org/abs/2310.08560
- Anthropic, Effective context engineering for AI agents — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Liu et al., Lost in the Middle — https://arxiv.org/abs/2307.03172
- Chroma, Context Rot — https://www.trychroma.com/research/context-rot
- NoLiMa — https://arxiv.org/abs/2502.05167 *(32K sub-50% figures lightly-verified)*
- Kimi K2.5 model card (256K) — https://huggingface.co/moonshotai/Kimi-K2.5 *(orchestrator-verified)* · OpenRouter (262K) — https://openrouter.ai/moonshotai/kimi-k2.5

**Q5 — cheap-worker QC / cascades**
- Chen/Zaharia/Zou, FrugalGPT — https://arxiv.org/abs/2305.05176 *(orchestrator-verified 98%)*
- Ong et al., RouteLLM — https://www.lmsys.org/blog/2024-07-01-routellm/ · https://arxiv.org/abs/2406.18665
- OpenAI Structured Outputs — https://developers.openai.com/api/docs/guides/structured-outputs *(orchestrator-verified)* · launch blog https://openai.com/index/introducing-structured-outputs-in-the-api/ *(100%/<40% [tier-1], fetch-blocked)*
- Zheng et al., Judging LLM-as-a-Judge — https://arxiv.org/abs/2306.05685
- Dhuliawala et al., Chain-of-Verification — https://arxiv.org/abs/2309.11495

**Unverified / flagged (do not rely on):** Karpathy LLM-wiki *tweet* + three-layer structure; OpenClaw `HEARTBEAT.md`;
PicoClaw/NanoClaw-specific SOUL.md/MEMORY.md conventions; "Llama2-13B@15≈70B" figure; NoLiMa exact %; Ledger-State
Stigmergy (arXiv:2604.03997); AutoGen/LangGraph shared-state framework-doc claims.
