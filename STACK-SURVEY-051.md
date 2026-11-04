# ADM stack survey: what to borrow, wrap, build, or avoid (ADM-051)

Date: 2026-11-04. Written for the owner of ADM, who is not a programmer.

## 0. How to read this, and what it is not

**What I did.** I ran about 55 queries against GitHub's own search (stars, license, last-push date), downloaded 11 projects (read the README or relevant source of 10; Aider was downloaded but I relied on web sources for it), and ran 8 web searches in this round for facts GitHub cannot give (free-tier limits, Windows Sandbox, packaging, small-model results).

**What I did not do.**
- I did not run any of this software. Everything below about what a project does comes from its README, its source tree, or a web page. None of it is tested on your PC.
- I could not search Codeberg, GitLab, SourceHut or the Hugging Face API. The sandbox I work in blocks those hosts (HTTP 403 on connect). Web search found nothing relevant on GitLab. **Other git hosts are therefore NOT covered.** Hugging Face was reached only through web-search snippets.
- Star counts are what GitHub reports. Several are implausible for the age or size of the project (for example a 60,000-star plugin repo and a 312,000-star skills repo). Stars are popularity, not quality, and can be inflated. I did not use them to rank anything.

**Requirements this survey is judged against** (your words, from the chats and this session):
1. One Windows 11 app for a non-programmer; plain-language request in, working app out.
2. You never have to babysit it; one instruction starts the work.
3. Free only: local models first, then genuinely free cloud tiers, never paid.
4. Works on **your 16 GB, SATA-SSD PC**; slow is acceptable.
5. AI involved in every step; local checks and cached verified code run before any AI call.
6. Honest test evidence; generated code isolated (no internet, nothing outside the project folder).
7. Windows EXE first; existing projects accepted too; web and APK later.

## 1. Short answer

No project found does what ADM must do end to end, on plain Windows, on 16 GB, for free. The useful finds are ideas and small components, not a replacement.

| Function | Verdict | One-line reason |
|---|---|---|
| Agent loop | **Build, copying the design of mini-swe-agent** | A small bash-only loop (MIT, one 190-line file) that works with any model, including ones with no tool-calling. |
| Making small models work | **Borrow ideas from little-coder** | Same 9.7B model scored 19.1% in vanilla Aider and 45.6% in little-coder (author's own runs). The harness matters as much as the model. |
| Spec, approval, independent verifier | **Borrow ideas from Pullboard and Superpowers** | Approved spec rows, a frozen acceptance bar, a second checker. Both need Node; neither is tested on Windows or small models. |
| Local model engine | **Keep Ollama; add any OpenAI-compatible local server** | Janas is real but experimental and tuned on one 32 GB Intel laptop. |
| Free cloud tiers | **Build a thin client; optionally accept FreeLLMAPI's URL** | Free tiers are shrinking and some use your prompts for training. |
| Token savings | **Build simple rules; skip the compression tools** | Measured gains are small on code and error text; local models have no token bill. |
| Code index | **Build with Python's own `ast` module** | Generated apps are Python at first; no dependency needed. |
| Windows sandbox | **Do not rely on a plain restricted token; test first** | There is a reported failure mode that would break ADM's output capture. See section 5. |
| Windows Sandbox (Pro) | **Use as the strong tier** | Built into your edition, supports no-network and a mapped folder. |
| Packaging | **EXE: PyInstaller (already works). APK: defer.** | Android needs Flutter or Android SDK plus Android Studio, 8 GB RAM minimum, 11 GB disk. |

## 2. Agent loop and small-model harness

| Project | Facts (from README or source) | License | Fit for ADM |
|---|---|---|---|
| SWE-agent/mini-swe-agent | The agent file is 190 lines of Python (the README says about 100 lines for the agent class). Only tool is bash. History is a plain list of messages. Each action is a fresh `subprocess.run`, so swapping in a sandbox means replacing one call. Works with any model via litellm. Authors report over 74% on SWE-bench Verified (with strong models). | MIT | **Best design to copy.** The sandbox-friendliness is exactly what ADM needs. The 74% is not evidence for small local models. |
| itayinbarr/little-coder | Built on `pi` (Node 22.19+). About 27 small extensions: write guard (refuses clobbering files), read-before-edit, quality monitor (empty, hallucinated, loop detection), thinking-budget cap, context watchdog, per-phase models (plan big, implement small), knowledge injection. Tuned for local llama.cpp, Ollama, LM Studio. | Apache-2.0 | **Borrow the mechanisms, not the code** (Node, TypeScript). |
| Aider-AI/aider | Repo map, many edit formats. Last push 2026-05-22 (slower than others). A blog author found that for qwen3-coder the `whole` edit format fixed a 0/100 result caused by unparseable diffs. | Apache-2.0 | Lesson: **edit format must match the model.** |
| anomalyco/opencode | Large, active terminal agent. | MIT | Not needed; it is another whole agent. |
| openai/codex | Active terminal agent. Contains the Windows sandbox (section 5). | Apache-2.0 | Useful as a source of Windows sandbox ideas only. |
| OpenHands/OpenHands | Full platform. Default sandbox is Docker; Windows is via WSL2. | MIT | **Avoid**: Docker/WSL2 is not one-click for a non-programmer. |
| Roo-Code | Archived on GitHub. | Apache-2.0 | Avoid. |

**The strongest finding for your 16 GB PC.** little-coder's own repository documents a controlled comparison: Qwen3.5 9.7B (Q4_K_M), same 225-exercise Aider Polyglot suite, same context size. Vanilla Aider passed 43 of 225 (19.11%); little-coder passed 45.6% on average. Caveats: this is the author's own measurement, not independent; the little-coder runs took about 22 hours of wall time; Polyglot exercises are small single-function tasks, not whole apps.

**Other evidence on small models (web, mixed quality).**
- One blog compared 23 local models. The `pi` agent with devstral and qwen3-coder timed out on both simple tasks, because those models lacked the habit of calling tools in sequence until a test passes. The author concluded Aider suited local 14B to 30B models. This supports a bash-only text protocol over native tool-calling.
- A forum answer says 7B to 12B models are not adequate for full agentic app-building. Another source puts Devstral Small 24B as the one reliable multi-file local option, but too slow on 16 GB (about 18 tokens/second with CPU offload).
- Implication: **ADM must expect the local model to fail often, and must be built to escalate (a different approach, then a free cloud tier, then a written blocker) rather than loop forever.**

## 3. Spec, approval and verification methods

- **Pullboard** (pullboard-dev/pullboard, MIT, v0.9.3). Method: you approve rows in a spec file; an item's acceptance bar is frozen when an agent claims it; a *second agent* verifies the exact commit; every claim and rejection is logged; git hooks enforce rules. Requires Node 22.13+. The README says: **"CI runs on Linux and macOS. Windows isn't tested yet."** It is built around Claude Code and Codex style agents. Not usable as a dependency. **The method is worth copying**, and it matches your "second AI checks the first" requirement.
- **Superpowers** (obra/superpowers, MIT). A set of 15 markdown skills (brainstorming, writing-plans, test-driven-development, systematic-debugging, verification-before-completion, requesting-code-review, subagent-driven-development, and others) that plug into coding agents such as Claude Code, Codex, Cursor, Gemini CLI, OpenCode. Flow: ask what you really want, show a short spec for sign-off, write a test-first plan, run subagents task by task with review. **Borrow the flow and the wording of the skills as prompts** (MIT allows this).
- **Fit with ADM:** ADM's plan-then-Approve screen, failing tests always block acceptance, and a separate review pass all come straight from these.

## 4. Local inference

| Project | Facts | License | Verdict |
|---|---|---|---|
| ollama/ollama | What ADM uses now. | MIT | **Keep as default.** |
| ggml-org/llama.cpp | The engine under most local tools. | MIT | Possible second backend. |
| janhq/jan | Desktop app with an OpenAI-compatible local server (127.0.0.1:1337/v1). GitHub lists its license as "other"; an earlier source said AGPL. **I did not verify the license text.** | unverified | Talk to it over HTTP only if the user already has it. |
| mudler/LocalAI | OpenAI-compatible server. | MIT | Optional. |
| Mintplex-Labs/anything-llm | Desktop chat and document-search app. | MIT | **Not needed.** It is a chat product, not a build engine. |
| prabanta-dev/janas ("Janas-LLM") | C program, no dependencies, streams large mixture-of-experts models from disk. Linux and Windows 10/11 x86-64 downloads. Headline: Qwen3-Next-80B (48 GB) at 26 tok/s writing on a 32 GB laptop (Intel Core Ultra 9, NVMe). README says: **"This is an experiment, not a product."** Developed and run on **one** machine. It "fills the free memory with its expert cache and reads the disk at full speed", and can push a desktop into swap. | GPL-3.0 | **Watch, do not depend.** Your PC has 16 GB and a SATA SSD (slower than the NVMe in its tests), and it is GPL (call it as a separate program, never copy its code into ADM). |
| Edge0 | Earlier check: Windows engine open-sourced 2026-09-30; benchmarks on Apple hardware; its own docs say agent/tool use is not optimized. | Apache-2.0 | Watch. |

Models that fit 16 GB, per web sources (unverified by me): Qwen2.5-Coder 7B (about 4.7 GB at Q4); Qwen3 8B; a 30B mixture-of-experts model (about 3B active) is said to reach 20 to 30 tok/s on 8 GB GPU plus 16 GB RAM. ADM currently offers only 1.5B, 3B and 7B Qwen2.5-Coder models.

## 5. Isolating generated code on Windows (the critical gap)

| Approach | What it does | Problem for ADM |
|---|---|---|
| Job Object only | Caps memory, CPU, process count; kills the process tree. | No network block, no file confinement. |
| Restricted token (WRITE_RESTRICTED) | Limits where the process can write. | **Reported failure.** The repository yzyyohh/dsh-windows-sandbox-0xc0000142 documents (with a results file) that a process under a WRITE_RESTRICTED sandbox cannot start native child programs when its output is captured through pipes: it gets "Access denied" and a Windows loader error 0xC0000142 pop-up. The same command with file redirection works. It is a third-party reproduction on another vendor's sandbox. **I have not reproduced it.** ADM captures output through pipes. |
| Dedicated low-privilege local user plus file permissions | Runs the code as a separate Windows account that can only write in the project folder. Optional firewall rule blocks its network. | Needs administrator rights once to create the account and set permissions. This is the approach in openai/codex (Rust, Apache-2.0, `windows-sandbox-rs`, about 21,000 lines in its top-level source files: sandbox users "CodexSandboxOffline" and "CodexSandboxOnline", permission lists, firewall setup, a private desktop) and in PHPCraftdream/wuserbox (Go, MIT OR Apache-2.0: one local account per project, administrator rights to grant write access). wuserbox has near-zero stars and an unproven track record. |
| Sandboxie-Plus | Kernel-driver sandbox. 19.8k stars. | GPL-3.0 and a kernel driver. **Avoid embedding.** |
| Docker / WSL2 (OpenHands, SWE-ReX) | Strong isolation. | Not one-click for a non-programmer. |
| **Windows Sandbox (Pro, your edition)** | Microsoft documents: needs Pro/Enterprise/Education; networking can be disabled in the `.wsb` file; folders can be mapped from the host, optionally read-only; the sandbox is thrown away on close; networking is **on by default**; **changes to a writable mapped folder persist and can affect the host.** Needs virtualization enabled and the feature switched on (administrator, reboot). A non-Microsoft note says `wsb exec` returns no output (fire and forget). I did not verify that. | Strong and built in. Design must pass results out through the one writable folder. |

**Recommendation (changes my earlier plan).**
1. **Strong tier:** Windows Sandbox: no network, project mapped read-only, one separate writable results folder, results copied out and verified by ADM.
2. **Fallback tier:** dedicated local sandbox account (the Codex / wuserbox pattern). Needs a one-time administrator step.
3. **Drop "plain restricted token" as a tier** until a Windows CI experiment shows pipe capture works.
4. **Experiments I can run now on the GitHub Windows runner:** (a) restricted token with pipe capture; (b) Job Object limits; (c) create a local user, set permissions, run a child process as it with pipes and a blocked network rule. The Windows Sandbox tier cannot be proven there (needs virtualization); you would run a short script on your PC.

## 6. Free cloud tiers (the "free, never paid" policy)

- **tashfeenahmed/freellmapi** (MIT, Node 20 to 24, Windows installer in Releases). One OpenAI-compatible endpoint over 34 providers with failover, per-key rate counters, encrypted keys, 635 model endpoints, an opt-in response cache. Its own README says: **"for personal experimentation and learning, not production"**, and that the effective model quality dips late in the day as top models hit daily caps. Its headline "7.4 billion free tokens per month" is the project's own total; I did not verify it.
- **Facts from web pages (reviewed Sept to Oct 2026, not first-hand):**
  - Groq free plan: 30 requests/minute, 1,000/day on some models.
  - OpenRouter `:free` models: 20 requests/minute, 50/day.
  - Google AI Studio: stopped publishing free limits on its docs page; moved Pro models to paid in April 2026; on the free tier Google says it uses prompts and responses to improve its products.
  - **Cerebras now requires a payment method** for its $5, 30-day credit. That conflicts with "never paid" unless you decide a card on file is acceptable.
  - GitHub Models was reported retired on 2026-07-30. Many "free API" lists still include it.
- **Consequences for ADM:** free cloud is an *optional helper*, never the foundation. Your code may be used for training on some tiers, so ADM must tell you before sending anything. ADM should keep a short, editable provider list and handle 429 errors by switching, not by retrying.
- **Router projects:** RouteLLM last pushed 2024-08-10 (stale). LiteLLM license field says "other"; unverified. Bifrost, Switchyard, new-api and others exist; none is needed if ADM only needs "try local, then the next free endpoint".

## 7. Saving tokens, caching, and repo maps

- **Compression tools** (LLMLingua MIT, needs an ML model; sqz Apache-2.0/MIT; others). sqz's own measured average is **24.7%** across 3,003 real compressions; it reports **0%** on source code and stack traces, and "up to 92%" only for output the model already has. These tools target paid cloud agents. On local models there is no token bill. **Skip.**
- **What does help a small local model:** keep full logs on disk and show only the failing excerpt; remove repeated lines; send line ranges, not whole files; keep prompts under the 8,192-token window ADM already sets. These are simple rules to write ourselves.
- **Caching.** Semantic caches (GPTCache MIT, Bifrost, others) match *similar* questions. For code, near-duplicate prompts can need different code, so a semantic hit can return the wrong answer. Safer: **exact-match cache, plus a cache of verified fixes keyed on the failing test's signature**, checked before any AI call. This is your "verify before spending tokens" idea.
- **Repo maps:** several MCP code-graph tools exist (CodeGraphContext MIT, others; Node or Rust). ADM's first generated apps are Python, so Python's built-in `ast` module can list files, functions and classes with no dependency. Build it.

## 8. Packaging

- **EXE:** PyInstaller, already proven on the Windows runner. Nuitka is AGPL-3.0: avoid.
- **APK:** Flet's `flet build apk` needs Flutter plus the Android SDK; Flutter's own Windows page lists a minimum of 8 GB RAM (16 recommended), 11 GB free disk, and the full Android Studio. BeeWare Briefcase (BSD-3-Clause) can package Android on Windows and installs its own JDK, but still downloads the Android toolchain and Gradle dependencies. **Heavy for a 16 GB PC and a first-run experience for a non-programmer. Defer APK.**
- **Web:** deferred by your decision.

## 9. Conflicts with your requirements (so you can veto)

- Codex (paid account) and Cerebras (card required) conflict with "never paid".
- Pullboard, little-coder and FreeLLMAPI need Node. That conflicts with "one self-contained app" unless ADM runs them as separate bundled programs.
- OpenHands and SWE-ReX assume Docker or WSL2.
- Janas is GPL-3.0 and tuned for different hardware.

## 10. Proposed build order (nothing started)

1. Windows CI experiments for the sandbox (restricted token with pipes, dedicated user, Job Object).
2. Sandbox adapter: Windows Sandbox as the strong tier, dedicated user as the fallback.
3. The mini-swe-agent-style loop (bash-only, text protocol) behind that adapter, with little-coder's guards (write guard, read-before-edit, loop and empty-output detection, thinking budget, context watchdog).
4. Plan-then-Approve screen and request box in the window (new project and existing project).
5. Verified-fix cache and failing-excerpt rules before any AI call.
6. Escalation ladder: local model, then a different approach, then a free cloud tier, then a written blocker.
7. Real-model proof on your PC (needs you to run it).

## 11. Unverified or open

- Every performance number above is from a README or web page, not from a run by me.
- Jan's license text; LiteLLM's license text; FreeLLMAPI's token totals and its per-provider terms review.
- Whether the restricted-token pipe failure reproduces on Windows 11 and on ADM's way of spawning processes.
- Whether `wsb` commands can capture output.
- Whether Windows Sandbox is enabled and virtualization is on in your BIOS.
- wuserbox quality and maturity.
- Other git hosts (Codeberg, GitLab, SourceHut, Hugging Face API) were not searched.

## Appendix A. Raw GitHub search results (as returned 2026-11-04)

Columns: repo | stars | license | last push | archived | description. Stars are popularity only; some counts look inflated. Not every row is relevant; irrelevant matches are left in so you can see what the search returned.

```
### compression  ::  prompt compression llm
microsoft/LLMLingua | 6802* | mit | pushed 2026-09-10 |  | [EMNLP'23, ACL'24] To speed up LLMs' inference and enhance LLM's perceive of key information, compress the pro
jia-gao/leanctx | 321* | mit | pushed 2026-08-22 |  | Drop-in prompt compression for production LLM apps. Cut your token bill 40-60% without changing your code. Pyt
baiibayu/srouter | 63* | mit | pushed 2026-11-04 |  | Never hit rate limits again. One OpenAI-compatible endpoint for 60+ providers & 1,200+ models — smart auto-fal
codexlx/contextshield | 26* | mit | pushed 2026-10-29 |  | 🛡️ Pack any codebase into a token-optimized, security-hardened LLM prompt. AST skeleton compression (saves up 
sriinnu/clipforge-PAKT | 20* | mit | pushed 2026-10-30 |  | Lossless-first prompt compression for JSON, YAML, CSV, and Markdown. Library, CLI, MCP server, desktop app, an
danielle34/cavewoman | 20* |  | pushed 2026-10-25 |  | Caveman prompting, measured. A two-channel evaluation framework for prompt compression and LLM token efficienc
imperativelabs/untoken | 15* | mit | pushed 2026-03-10 |  | Token compression for LLM prompts via a learned token selector.
UmaiTech/aura-llm-gateway | 12* | mit | pushed 2026-10-23 |  | High-performance Rust LLM gateway implementing the Open Responses API. Unified access to OpenAI, Anthropic, Go
zerocoolailabs/fitcode2prompt | 10* |  | pushed 2025-07-15 |  | A CLI tool to fit your codebase into a single LLM prompt offering fine grained compression control and AI powe
AIAnytime/Prompt-Compression-using-LLMLingua | 8* | mit | pushed 2023-12-17 |  | Prompt Compression using LLMLingua. It helps with token's cost and latency.

### compression2  ::  context compression coding agent
Paritok-official/paritok-4b-v1 | 1442* | apache-2.0 | pushed 2026-10-06 |  | Non-destructive compression gateway for AI coding agents. Cuts token bills 25% on turn 1 to past 85% in long o
ojuschugh1/sqz | 674* | apache-2.0 | pushed 2026-10-22 |  | Context compression for AI coding agents: compresses tool output before it enters the model, dedups repeats to
ooples/token-optimizer-mcp | 568* | mit | pushed 2026-11-04 |  | Measure token savings per AI coding agent, optimize context, and share a live local knowledge graph across 16 
activeing123/mcptoon | 420* | apache-2.0 | pushed 2026-11-04 |  | One zero-dependency MCP gateway CLI for every server and agent skill. Token optimization, tool discovery and c
zszszszsz/.config | 364* | mit | pushed 2023-10-05 |  | # # Automatically generated file; DO NOT EDIT. # OpenWrt Configuration # CONFIG_MODULES=y CONFIG_HAVE_DOT_CONF
LearnPrompt/cc-harness-skills | 240* | mit | pushed 2026-07-10 |  | Portable CC-inspired skills for memory, verification, multi-agent coordination, context compression, and proac
DerekYRC/mini-claude-code | 169* |  | pushed 2026-07-07 |  | mini-claude-code: a simplified Java Claude Code agent distilling core Agent Harness mechanisms. Features: Agen
jettbrains/-L- | 169* | gpl-3.0 | pushed 2021-08-18 |  | W3C Strategic Highlights  September 2019  This report was prepared for the September 2019 W3C Advisory Committ
Supercompress/Supercompress | 140* | mit | pushed 2026-11-04 |  | Query-aware context compression for LLMs and coding agents. Cut ~65% of input tokens.
recranvvi5c/ContextCrucible | 136* | mit | pushed 2026-10-21 |  | Budget-aware context compiler for coding agents - scan, grade, spark-test and pour a hard-budget context pack

### cmdoutput  ::  cli output compression tokens llm agent
ojuschugh1/sqz | 674* | apache-2.0 | pushed 2026-10-22 |  | Context compression for AI coding agents: compresses tool output before it enters the model, dedups repeats to
dean0x/skim | 31* | mit | pushed 2026-09-29 |  | The most intelligent context optimization engine for coding agents. Code-aware AST parsing across 17 languages
dPeluChe/trs | 15* | mit | pushed 2026-11-04 |  | Token-Reducing Shell — terminal output compression for AI coding agents
phuetz/lm-resizer | 4* | apache-2.0 | pushed 2026-10-12 |  | Rust-native context compression for Claude Code, Codex & MCP agents: filters & compresses noisy tool output (t
NatBrian/image-token-compression | 3* | mit | pushed 2026-07-10 |  | LLM token compression via images: a transparent Antrhopic/OpenAI proxy that renders agent context (system prom
lesterppo/hermes-token-efficiency | 3* | other | pushed 2026-09-30 |  | Cut LLM token consumption 65-80% in Hermes Agent — RTK (tool-output) + Caveman (agent-output) compression plug
zulfff/lelouch | 1* | mit | pushed 2026-07-22 |  | ⚡ Absolute command over your AI agent's token budget — local-first compression of noisy tool output before it 
abhijitbansal/cartoon | 1* | mit | pushed 2026-10-29 |  | Token-optimized output for any CLI — your AI agent reads 12 lines instead of 800, raw log always archived. Ada

### semcache  ::  semantic cache llm
maximhq/bifrost | 9370* | apache-2.0 | pushed 2026-11-04 |  | Open-source, high-performance AI gateway that works as your LLM gateway, MCP gateway and agent gateway. One Op
zilliztech/GPTCache | 8219* | mit | pushed 2026-09-22 |  | Semantic cache for LLMs. Fully integrated with LangChain and llama_index. 
codefuse-ai/ModelCache | 931* | other | pushed 2025-06-30 |  | A LLM semantic caching system aiming to enhance user experience by reducing response time via cached query-res
thu-nics/C2C | 769* | apache-2.0 | pushed 2026-10-28 |  | [ICLR'26] The official code implementation for "Cache-to-Cache: Direct Semantic Communication Between Large La
messkan/prompt-cache | 426* | mit | pushed 2026-08-18 |  | Cut LLM costs by up to 80% and unlock sub-millisecond responses with intelligent semantic caching.A drop-in, p
upstash/semantic-cache | 304* | mit | pushed 2024-11-21 |  | A fuzzy key value store based on semantic similarity rather lexical equality.
peva3/SmarterRouter | 155* | mit | pushed 2026-05-10 |  | SmarterRouter: An intelligent LLM gateway and VRAM-aware router for Ollama, llama.cpp, and OpenAI. Features se
colossus-lab/openarg_backend | 150* | mit | pushed 2026-11-03 |  | AI-powered analysis engine for Argentine government open   data. Multi-agent pipeline (LangGraph) with 10 data
sensoris/semcache | 99* | mit | pushed 2026-01-02 |  | Semantic caching layer for your LLM applications. Reuse responses and reduce token usage.
aqstack/mimir | 94* | mit | pushed 2025-12-24 |  | mimir is a drop-in proxy that caches LLM API responses using semantic similarity, reducing costs and latency f

### routing  ::  llm router cost
QuantumNous/new-api | 51365* | agpl-3.0 | pushed 2026-11-04 |  | Open-source AI gateway. Self-hosted LLM gateway with OpenAI-, Claude- and Gemini-compatible APIs, model routin
coaidev/coai | 9347* | apache-2.0 | pushed 2026-03-12 |  | 🚀 Next Gen Multi-tenant AI One-Stop Solution. Builtin Admin & Billing System. Enterprise-Grade Unified LLM Gat
NVIDIA-NeMo/Switchyard | 3483* | apache-2.0 | pushed 2026-11-04 |  | Switchyard lets LLM applications route traffic across models and providers while preserving native OpenAI and 
fuxicodex/Fuxi | 3196* | other | pushed 2026-10-20 |  | FuXi is a fast, self-contained AI coding agent that lives in your terminal — edit code, run commands, and driv
open-compress/claw-compactor | 2003* | mit | pushed 2026-04-01 |  | 14-stage Fusion Pipeline for LLM token compression — reversible compression, AST-aware code analysis, intellig
ENTERPILOT/GoModel | 1302* | mit | pushed 2026-11-04 |  | AI gateway / AI control plane / AI proxy written in Go. Unified OpenAI-compatible and Anthropic-compatible API
modu-ai/moai-adk | 1250* | apache-2.0 | pushed 2026-11-03 |  | Agentic development harness for Claude Code — SPEC-driven plan/run/sync, TRUST 5 quality gates, model+effort r
CommonstackAI/UncommonRoute | 702* | mit | pushed 2026-06-26 |  | Automatic LLM router — 82% cost savings, 79.4% accuracy, 93.4% pass rate. Drop-in OpenAI proxy.
NadirRouter/NadirClaw | 661* | other | pushed 2026-11-04 |  | Source-available LLM router and AI cost optimizer. Routes simple prompts to cheap or local models and complex 
QuintinShaw/pi-dynamic-workflows | 590* | mit | pushed 2026-10-27 |  | Claude Code–style dynamic workflows for Pi: code-mode subagents with real model routing, journaled resume, git

### gateway  ::  llm gateway proxy openai compatible
ENTERPILOT/GoModel | 1302* | mit | pushed 2026-11-04 |  | AI gateway / AI control plane / AI proxy written in Go. Unified OpenAI-compatible and Anthropic-compatible API
Mirrowel/LLM-API-Key-Proxy | 559* | other | pushed 2026-11-02 |  | Universal LLM Gateway: One API, every LLM. OpenAI/Anthropic-compatible endpoints with multi-provider translati
Nayjest/lm-proxy | 157* | mit | pushed 2026-11-03 |  | OpenAI-compatible HTTP LLM proxy / gateway for multi-provider inference (Google, Anthropic, OpenAI, PyTorch). 
AprilNEA/BYOKEY | 140* | other | pushed 2026-10-11 |  | Turn AI subscriptions into standard API endpoints. OpenAI & Anthropic compatible gateway — for Amp Code, Curso
Felix-au/OmniKey-AI-Unified-Key-Manager | 134* | mit | pushed 2026-10-13 |  | A self-hosted LLM proxy and failover gateway supporting OpenAI & Gemini compatible endpoints. Routes requests 
VkRainB/ccMesh | 128* | apache-2.0 | pushed 2026-10-27 |  | Claude Code / Codex local AI proxy gateway desktop app (Tauri). Anthropic Messages <-> OpenAI-compatible proto
openziti/llm-gateway | 104* | apache-2.0 | pushed 2026-10-14 |  | Zero trust LLM gateway. OpenAI-compatible proxy with semantic routing and load balancing across OpenAI, Anthro
liyueyuan123/llm-api-gateway | 100* | mit | pushed 2026-06-08 |  | Self-hosted AI API gateway: OpenAI-compatible reverse proxies + aggregation gateway + tooling on your own VPS
apimartd9uqov94/llm-api-proxy-cost-guide | 87* | other | pushed 2026-10-12 |  | AI API gateway / relay: 307 models behind one OpenAI-compatible key. image2.5 $0.0085/image, Seedance 2.0 Mini
KochC/opencode-llm-proxy | 86* | mit | pushed 2026-10-29 |  | Local OpenCode-backed LLM gateway for OpenAI, Anthropic, Gemini, and Responses API-compatible tools, with stre

### freeapi  ::  free llm api
unclecode/crawl4ai | 86905* | apache-2.0 | pushed 2026-11-04 |  | Official Crawl4AI Cloud: a hosted web scraping, extraction, and search API for AI agents. Free API key, 1,000 
Ebony-Vinyl/dsh-our-free-model | 60667* | mit | pushed 2026-11-04 |  | 在 dsh 里装上这个插件即可，无需登录、注册或填 API Key，就能使用包括 DeepSeek V4.1 Flash、Kimi K3 在内的前沿模型——完全�
mnfst/awesome-free-llm-apis | 12225* | cc0-1.0 | pushed 2026-11-04 |  | List of Permanent Free LLM API  (API Keys)
Arthur-Ficial/apfel | 6549* | mit | pushed 2026-10-14 |  | The free AI already on your Mac. CLI tool, OpenAI-compatible server, and interactive chat — all on-device via 
open-free-llm-api/awesome-freellm-apis | 5141* | mit | pushed 2026-10-27 |  | 134+ free LLM APIs & AI API keys from 40+ providers. Google Gemini, NVIDIA NIM, Groq, OpenRouter & more. One-c
theJayTea/WritingTools | 2481* | gpl-3.0 | pushed 2026-08-19 |  | The world's smartest system-wide grammar assistant; a better version of the Apple Intelligence Writing Tools. 
zebbern/no-cost-ai | 2393* | mit | pushed 2026-09-21 |  | 80+ free AI services for chat, image, video, voice & APIs (may sometimes include access to lead gen ai models 
jwadow/kiro-gateway | 2351* | agpl-3.0 | pushed 2026-05-18 |  | 👻 Proxy API gateway for Kiro IDE & CLI (Amazon Q Developer / AWS CodeWhisperer). Use free Claude models with a
travisvn/openai-edge-tts | 2149* | gpl-3.0 | pushed 2025-07-01 |  | Free, high-quality text-to-speech API endpoint to replace OpenAI, Azure, or ElevenLabs
Amm1rr/WebAI-to-API | 1405* | mit | pushed 2026-11-01 |  | Webchat to API
ShaikhWarsi/free-ai-tools | 1078* | mit | pushed 2026-10-11 |  | Curated list of free and low cost AI tools, LLM APIs, IDEs, agents, and infrastructure for building real AI ap
CelaDaniel/free-ai-resources-x | 988* | mit | pushed 2026-05-21 |  | 🌟 A curated collection of free, high quality AI tools 🤖, APIs 🔗, datasets 📊, and learning resources 📚 covering

### freeapi2  ::  free-llm-api-resources
abbosaliboev/free-ai-bible | 203* | mit | pushed 2026-10-22 |  | 🧠 The Ultimate Directory of Free AI APIs & Tools for Developers 2026 — Free LLM APIs, Image Generation, Model 
jtig37/free-llm-api-resources | 155* |  | pushed 2024-08-21 |  | A list of free LLM inference resources accessible via API.
CYBIRD-D/FREE-LLM-API-Provider | 118* |  | pushed 2026-11-02 |  | This is a list of free LLM provider resources accessible via API. Including some cn platform  免费llm api平台（包括cn
nherx/free-llm-api-resources | 34* |  | pushed 2026-10-12 |  | 🤖 Discover free API access and credits for various legitimate large language model services in one curated res
xinrui-z/free-llm | 26* | mit | pushed 2026-05-20 |  | 🔥 Free LLM APIs & Resources List — collect free GPT / Claude / open-source LLM endpoints, tools and guides for
Krushnaapatil/free-llm-api-resources | 22* |  | pushed 2026-05-21 |  | Free LLM API Resources is a curated list of providers that offer free access or trial credits for API-based LL

### repomap  ::  repo map tree-sitter code context llm
tirth8205/code-review-graph | 32592* | mit | pushed 2026-10-29 |  | Local-first code intelligence graph for MCP and CLI. Builds a persistent map of your codebase so AI coding too
bettyabay/Codebase-Understanding-Agent | 3* |  | pushed 2026-03-14 |  | Multi-agent codebase intelligence system for rapid onboarding to brownfield data engineering repos. Builds liv
unixsysdev/repomap | 1* |  | pushed 2025-10-05 |  | Tree-sitter repository maps and ranked code context for LLM applications
FrxshSpamzL2/csharp_Repomap_for_Agent | 0* |  | pushed 2026-10-13 |  | 🗺️ Enhance AI agents for C# codebases by creating intelligent code maps that improve efficiency and reduce con

### codeindex  ::  code indexing mcp symbol retrieval
Atypical-Consulting/ASTral | 4* | other | pushed 2026-10-31 |  | Structured code retrieval for AI agents — index once with tree-sitter, query symbols precisely via MCP. Cut co
BigJai/codemunch-pro | 3* | mit | pushed 2026-03-02 |  | Intelligent code indexing MCP server. 13 tools, 10 languages, hybrid search, call graphs, O(1) symbol retrieva
ahmadsurti/CodebaseRAG-LanceDB-TreeSitter-MCP-Based-Symbol-Aware-Codebase-Retrieval-System | 0* | apache-2.0 | pushed 2026-09-22 |  | Self-updating, symbol-aware vector index and relational call graph of codebases exposed over MCP
joh09876544/quickcontext | 0* | agpl-3.0 | pushed 2026-10-12 |  | Provide fast local code search, indexing, and retrieval using Rust and Python tools with AI-assisted context a
Phyzx72/sourcelens | 0* | mit | pushed 2026-10-26 |  | Token-efficient local code retrieval MCP server — index a codebase once with tree-sitter, query exact symbols 

### agents  ::  autonomous coding agent software engineer
aserhat81/OpenZion | 15* |  | pushed 2026-03-03 |  | Local AI Software Engineer for VS Code. Supports Ollama/LM Studio, autonomous agentic loops, web search, and w
richardrx/autonomous-engineering | 12* | mit | pushed 2026-10-31 |  | A practical blueprint for building software with AI agents: independent code review, risk-based approvals, ver
Ranjitpatra26/DevCore-AI- | 7* |  | pushed 2026-07-29 |  | DevCore AI is an autonomous multi-agent AI software operating system powered by 13 specialized AI engineer per
dev-karthikeyan/autonomous-software-engineer | 5* |  | pushed 2026-06-20 |  | Multi-agent AI system that analyzes requirements, creates project plans, generates code, and builds software p
ulpi-io/autonomous-engineering | 3* |  | pushed 2026-08-18 |  | Autonomous software delivery for AI agents. 18 skills that turn the lifecycle into bounded, self-correcting, c
lucianoayres/agentic-software-engineering-for-leaders-handbook | 3* |  | pushed 2025-03-24 |  | Agentic Software Engineering for Leaders is a comprehensive handbook for software engineering managers, aspiri
tjmustard/Hypergraph-Coding-Agent-Framework | 2* | mit | pushed 2026-09-28 |  | A rigorous, Spec-First framework for autonomous software engineering. Solves the Specification Alignment Probl
Ayushhgit/Claude_code_lite | 2* |  | pushed 2026-10-09 |  | REVI is an advanced, autonomous AI coding agent designed to operate with the systematic rigor of a Senior Soft
Tarekivida/ai_development_team | 2* | mit | pushed 2025-05-02 |  | Autonomous multi-agent AI development system built with AutoGen. Simulates a collaborative software team with 
YasirAzam6/AutoDev | 2* | mit | pushed 2025-06-13 |  | **AutoDev** is an agentic AI software engineer that understands high-level instructions, plans intelligently, 
Rancidgift57/Autonomous-Hierarchical-Software-Engineering-Agents | 1* |  | pushed 2026-09-03 |  | AHSEA is an autonomous hierarchical multi-agent software engineering system that transforms project ideas into
suhasagg/google-antigravity-autonomous-software-engineering-platform | 1* |  | pushed 2026-10-03 |  | Google Antigravity-inspired autonomous software engineering platform for agentic coding, multi-agent orchestra

### agents2  ::  ai coding agent terminal open source
QwenLM/qwen-code | 29012* | apache-2.0 | pushed 2026-11-04 |  | An open-source AI coding agent that lives in your terminal.
manaflow-ai/cmux | 28690* | other | pushed 2026-11-04 |  | Open source Ghostty-based macOS terminal with vertical tabs and notifications for AI coding agents. Built for 
plandex-ai/plandex | 15895* | mit | pushed 2025-10-03 |  | Open source AI coding agent. Designed for large projects and real world tasks.
generalaction/emdash | 6185* | apache-2.0 | pushed 2026-11-02 |  | Emdash is the Open-Source Agentic Development Environment (🧡 YC W26). Run multiple coding agents in parallel. 
PurpleDoubleD/locally-uncensored | 3283* | agpl-3.0 | pushed 2026-11-04 |  | The all-in-one local AI studio for your desktop: chat, image and video generation and a coding agent in one fr
StartupHakk/OpenMonoAgent.ai | 1915* | other | pushed 2026-11-04 |  | (BETA) AI shouldn't have a meter. Unlimited tokens. Forever. Your machine. Your agent. Use it from anywhere. T
leepokai/Codync | 1874* | apache-2.0 | pushed 2026-11-04 |  | Open source Grok Bot alternative, Bring your own agent and subscription: message Claude Code, Codex, Gemini CL
bradAGI/awesome-cli-coding-agents | 1450* |  | pushed 2026-11-02 |  | Curated directory of terminal-native AI coding agents and the harnesses that orchestrate them. Covers open-sou
vstorm-co/pydantic-deepagents | 1116* | mit | pushed 2026-10-30 |  | Open-source, self-hosted Claude Code - a terminal AI assistant and the Python framework behind it. Tool-callin
vinhnx/VTCode | 897* | apache-2.0 | pushed 2026-11-03 |  | VT Code is an open-source Rust terminal coding agent.
risa-labs-inc/BossConsole | 815* | apache-2.0 | pushed 2026-11-04 |  | Open-source, multi-platform harness for AI agents - a native, multi-threaded operator's console (JVM, not Elec
greenfield-inc/Pane | 602* | other | pushed 2026-11-04 |  | Terminal-first, open-source AI agent manager for any CLI agent (agent agnostic), any OS (mac, windows, linux).

### agentwin  ::  coding agent windows native local ollama
DevMando/MandoCode.Desktop | 5* | mit | pushed 2026-11-04 |  | The MandoCode AI coding agent as a native Windows app — WinUI 3 over the same open-weight-model engine as the 
otzpt/V-Agent | 1* | other | pushed 2026-11-04 |  | A native, GPU-accelerated code editor with local-first AI and no telemetry. A fork of Zed for Windows and Linu
h0rk1p/ollama-code | 0* | mit | pushed 2026-04-26 |  | Terminal-native AI coding agent powered by local Ollama models. Linux, macOS, Windows.
nathaniel-martin/AI-Workstation-Hub | 0* | mit | pushed 2026-05-03 |  | Portable Windows-native AI workstation for local Ollama models, Hugging Face GGUF import, diagnostics, and a w
ZStudio-lab/Gamma-Code | 0* | mit | pushed 2026-11-03 |  | A local-only, terminal-native AI coding agent for Windows. Talks only to Ollama on 127.0.0.1 — no cloud, no AP
Kortexio/CodeForge | 0* | mit | pushed 2026-11-03 |  | Open-source AI-native coding IDE built on Code-OSS. Bring your own models (cloud or local), agentic coding, me
X-AlphaCoder-X/sigil-code | 0* | agpl-3.0 | pushed 2026-10-30 |  | Open-source AI coding agent for your terminal, in plain Python. Works with any OpenAI-compatible model, includ
robertbackhaus-a11y/REAPER-AI | 0* | mit | pushed 2026-11-02 |  | Lightweight, local-first autonomous AI coding agent with persistent project memory, context-aware execution, c

### appbuilder  ::  ai app builder from prompt generate full application
Souvik-223/denzer | 1* | mit | pushed 2026-09-05 |  | A full-stack conversational AI app builder that generates and manages web applications from user prompts. Supp
api-evangelist/lovable | 1* |  | pushed 2026-10-30 |  | Lovable — independent third-party profile of a public API surface, by API Evangelist. Lovable is an AI app bui
nasertech9/ai-app-builder | 0* |  | pushed 2026-05-02 |  | AI-powered platform that generates full-stack applications from user prompts (UI, backend, database).
suman11pal02-hash/Web-Application-Builder | 0* |  | pushed 2026-08-15 |  | An AI-powered MERN stack web application builder that generates custom web apps from user prompts and provides
mehulnikam6195-byte/promptforge-ai | 0* |  | pushed 2026-05-01 |  | AI-powered app builder that generates full applications from a single prompt with live preview and smart code 
richabhawna/agentic-ai-app-builder | 0* |  | pushed 2026-07-08 |  | AI-powered application builder using LangGraph and LLMs that automatically plans, generates, debugs, and packa
rohitsharma27011/CodeGen-AI | 0* | mit | pushed 2026-06-10 |  | AI-powered full-stack app builder that generates, edits, and deploys applications from natural language prompt
TanujaBabar/ai_powered_web_app_builder | 0* |  | pushed 2026-03-24 |  | NxtBuild is a full-stack AI-powered web app builder built with React, Node.js, Express, and MongoDB that gener
Haswanthkumar11/NxtBuild---AI-powered-Web-App-Builder | 0* |  | pushed 2026-07-04 |  | Built a full-stack AI-powered web app builder that generates responsive applications from natural language pro
fidarahman18/ai_builder-jarvis-inspired- | 0* |  | pushed 2026-06-25 |  | Full-stack app generation pipeline, brain is GPT-4o. Takes a prompt, generates a Next.js application, scaffold

### orchestr  ::  multi-agent software development orchestrator
hoangsonww/AI-Agents-Orchestrator | 99* | mit | pushed 2026-09-27 |  | 🪈 Intelligent orchestration system that coordinates multiple AI coding assistants (Claude, Codex, Gemini CLI, 
untra/operator | 41* | mit | pushed 2026-11-01 |  | 📞 Operator! Multi-agent orchestration application for AI assisted kanban shaped software development
Navide-dev/Navide | 41* | mit | pushed 2026-11-04 |  | Navide is an open-source Agentic Development Environment (ADE) that orchestrates AI software teams across the 
markuswondrak/AgentMux | 38* |  | pushed 2026-05-17 |  | Deterministic multi-agent pipeline for end-to-end software development, orchestrating CLI-based AI tools (e.g.
jonnyzzz/run-agent | 31* | apache-2.0 | pushed 2026-05-17 |  | A multi-agent orchestration framework for AI-powered software development
OmegaMc1331/agentic-software-factory | 26* | mit | pushed 2026-10-26 |  | Open-source agentic software development platform for building, orchestrating and monitoring autonomous AI cod
mohamedameen-io/AutoDev | 24* | gpl-3.0 | pushed 2026-07-13 |  | Deterministic, resumable, tournament-based orchestrator for LLM-driven software development. Turns Claude Code
patil-shubham-dev/AgenticOS | 24* | mit | pushed 2026-08-29 |  | An open-source, self-hostable AI operating system and development workspace. Powered by Electron and React 19,
ronnycoding/.claude | 20* |  | pushed 2026-06-17 |  | Claude Code configuration featuring specialized AI agents, custom skills, automated GitHub workflows with Epic
berrzebb/consensus-loop | 16* |  | pushed 2026-03-22 |  | Claude Code plugin — structural guardrails for multi-agent software development. RTM-based evidence, cross-mod

### sandbox  ::  windows sandbox restricted token appcontainer job object

### sandbox2  ::  sandbox untrusted code execution agents
akshayaggarwal99/boxed | 14* | mit | pushed 2026-09-11 |  | The Sovereign Code Execution Engine for AI Agents. Run untrusted code safely locally or in the cloud using Doc
kweaver-ai/sandbox | 8* |  | pushed 2026-04-07 | ARCHIVED | Sandbox Runtime is a high-performance code execution service designed for AI Agent applications. It provides m
sakkshm/bastion | 2* |  | pushed 2026-04-22 |  | A sandboxed execution environment for AI agents to run untrusted code and manage files.
gojaildev/gojail | 2* | other | pushed 2026-10-17 |  | gojail is a self-hosted, sub-10ms Kubernetes-native execution sandbox designed to safely run untrusted AI agen
victorperson999/Vestibule | 1* | mit | pushed 2026-11-04 |  | Vestibule - A kernel-isolated code-execution sandbox for AI agents, as an MCP server. Run untrusted/questionab
shekhar-gupta-dev/secure-agent-sandboxes-demo | 1* | mit | pushed 2026-08-09 |  | Secure agent tool execution on Azure Container Apps Sandboxes: a disposable, network-locked microVM that runs 
tamilselvan04200803-max/autonomous-ci-repair-platform | 1* | apache-2.0 | pushed 2026-11-01 |  | Core Idea  Aegis Forge = autonomous CI/CD repair system that fixes failed GitHub workflows and provides indepe
kambizunfxb/nodejs-sandbox-security | 0* | mit | pushed 2026-05-14 |  | Enterprise security analysis of Node.js sandboxing risks, vm2 vulnerabilities, sandbox escape patterns, and se
AnuroopSaxena-code/AXES | 0* |  | pushed 2026-10-26 |  | Adaptive eXecution Environment Sandbox: A behavior-aware Linux runtime for autonomous agents and untrusted AI 
zzhiyuann/agent-sandbox | 0* | mit | pushed 2026-04-12 |  | Secure execution sandbox for AI agents. Run untrusted agent code safely with filesystem isolation, network con
Ralph-20/sandbox-demo | 0* |  | pushed 2026-07-29 |  | Vercel Sandbox demo — run untrusted code in a Firecracker microVM. Live demos: isolated execution, streaming, 
underdown/hermes-computer | 0* | mit | pushed 2026-10-05 |  | Sandboxed tool execution for Hermes Agent via Cloudflare Computer workspaces — no untrusted code touches your 

### localinf  ::  local llm inference engine windows
hongfaqiu/strata-manager | 50* | mit | pushed 2026-11-04 |  | Strata Manager makes Niko1221/Strata, the local LLM inference engine, easier to set up and use. Manage local m
fuxingliang/nova-studio | 5* | mit | pushed 2026-08-19 |  | Nova Studio - Windows desktop workbench for local LLM inference (vLLM / SGLang / llama.cpp via WSL2), bridging
dimohy/IgnisCore | 4* | apache-2.0 | pushed 2026-04-29 |  | IgnisCore — Experimental local LLM inference engine in C#/.NET with Vulkan Compute. Runs Gemma 4 GGUF models f
adamandama/Strata-Model-Importer | 3* | other | pushed 2026-11-04 |  | One-click GUI tool that plugs any fine-tuned, abliterated or community GGUF into the Strata local inference en
sirfyyn/fle-studio | 2* | mit | pushed 2026-10-31 |  | A local LLM chat and lab for llama.cpp and the FLE engine: GGUF model loader, live inference data, launch prof
ctctoo/LLMController | 1* | mit | pushed 2026-08-29 |  | A local LLM launcher and OpenAI-compatible API gateway for Windows that starts your own inference engine with 
KoboldCPP-Local-LLM-Server/.github | 1* |  | pushed 2026-09-21 |  | KoboldCPP delivers a single-executable, C++ accelerated local LLM inference engine built on llama.cpp. Feature
legislat/SimpleHarn | 0* | apache-2.0 | pushed 2026-11-04 |  | A simple unified endpoint and model swapper for local inference engines
mercwar/JOE-TRON-LLMA | 0* |  | pushed 2026-10-24 |  | A step-by-step developer tutorial and low-level C runtime guide for building a sovereign, zero-dependency GGUF
bricesommers/apus-qwen3.6-35B-A3B | 0* | other | pushed 2026-08-31 |  | Local inference engine for Qwen3.6-35B-A3B (35B-total / 3B-active hybrid-linear MoE, experts streamed from NVM

### ssdstream  ::  stream llm weights from ssd low memory inference

### layered  ::  layer-by-layer inference large model small gpu

### janas  ::  janas llm
prabanta-dev/janas | 604* | gpl-3.0 | pushed 2026-11-04 |  | 37 tok/s from Qwen3-Next-80B (48 GB) on a 32 GB laptop, 24 without drafts vs 2.8 for llama.cpp; reading 62 vs 
Jeferson-Schmidt/Janas-LLM | 0* |  | pushed 2026-10-28 |  | 
joaniberian9588/janas | 0* | mit | pushed 2026-10-13 |  | Run large mixture-of-experts language models on ordinary hardware with a dependency-free C toolset.
anurag965/OdiaGenAI_JanaSathi | 0* |  | pushed 2025-07-27 |  | Built a bilingual Retrieval-Augmented Generation (RAG) chatbot for Odisha government  schemes using OpenRouter
peak-flow/jana-ai | 0* |  | pushed 2026-01-26 |  | Local-first desktop notes with AI summaries. Jana pairs a distraction-free editor with one-click summarization
peak-flow/jana | 0* |  | pushed 2026-06-30 |  | Local-first desktop notes with AI summaries. Jana pairs a distraction-free editor with one-click summarization

### named-codeg  ::  codeg
colbymchenry/codegraph | 76573* | mit | pushed 2026-11-01 |  | Pre-indexed code knowledge graph, auto syncs on code changes, for Claude Code, Codex, Gemini, Cursor, OpenCode
swagger-api/swagger-codegen | 17795* | apache-2.0 | pushed 2026-11-04 |  | swagger-codegen contains a template-driven engine to generate documentation, API clients and server stubs in d
fuzhengwei/CodeGuide | 11924* | apache-2.0 | pushed 2026-11-01 |  | :books: 本代码库是作者小傅哥多年从事一线互联网 Java 开发的学习历程技术汇总，旨在为大家提供一个清晰详细的学习教程�
zai-org/CodeGeeX | 8794* | apache-2.0 | pushed 2024-08-13 |  | CodeGeeX: An Open Multilingual Code Generation Model (KDD 2023)
oapi-codegen/oapi-codegen | 8642* | apache-2.0 | pushed 2026-11-04 |  | Generate Go client and server boilerplate from OpenAPI 3 specifications
zai-org/CodeGeeX2 | 7508* | apache-2.0 | pushed 2024-07-10 |  | CodeGeeX2: A More Powerful Multilingual Code Generation Model

### named-pullboard  ::  pullboard
pullboard-dev/pullboard | 677* | mit | pushed 2026-10-28 |  | Autonomous development for real products. Governed agents build from specs you approve, follow the rules you s
pullboard/pullboard | 5* |  | pushed 2018-09-21 |  | A flexible dashboard that helps teams, maintainers, and contributors stay on top of open pull requests
JUTZUGC/pullboard-deploy-guide | 1* | mit | pushed 2026-11-02 |  | Pullboard 一键安装｜让 agent 按你批准的需求建，另一个 agent 验收｜第三方一键部署方案
chingu-voyages/V57-tier3-team-33 | 1* |  | pushed 2025-10-15 |  | PullBoard is your team's mission control for GitHub pull requests.  Get a real-time overview of all open and c
itshiroto/pullboard | 0* |  | pushed 2026-10-23 |  | 
pbrezina/pullboard | 0* | gpl-3.0 | pushed 2026-11-04 |  | 

### named-superpowers  ::  superpowers
obra/superpowers | 312409* | mit | pushed 2026-11-03 |  | An agentic skills framework & software development methodology that works.
payloadcms/payload | 45667* | mit | pushed 2026-11-04 |  | Payload is the open-source, fullstack Next.js framework, giving you instant backend superpowers. Get a full Ty
iamgio/quarkdown | 16346* | gpl-3.0 | pushed 2026-11-01 |  | 🪐 Markdown with superpowers: from ideas to papers, presentations, websites, books, and knowledge bases.
jnMetaCode/superpowers-zh | 8465* | mit | pushed 2026-10-26 |  | 🦸 AI 编程超能力 · 中文增强版 — superpowers（250k+ ⭐）完整汉化 + 4 个中国原创 skills，让 Claude Code / Copilot CLI / Hermes Agent / Cu
k8sgpt-ai/k8sgpt | 8296* | apache-2.0 | pushed 2026-11-04 |  | Giving Kubernetes Superpowers to everyone
tw93/Waza | 7509* | mit | pushed 2026-11-02 |  | 🥷 Engineering habits you already know, turned into skills AI assistants like Claude Code, Codex and Cursor can

### named-freellmapi  ::  freellmapi
tashfeenahmed/freellmapi | 47545* | mit | pushed 2026-11-04 |  | 7.4 billion tokens per month. 34 free LLM providers. 635 free model endpoints. All behind one /v1 endpoint, pl
open-free-llm-api/awesome-freellm-apis | 5141* | mit | pushed 2026-10-27 |  | 134+ free LLM APIs & AI API keys from 40+ providers. Google Gemini, NVIDIA NIM, Groq, OpenRouter & more. One-c
sunsky89757/freellmapi | 77* |  | pushed 2025-06-12 |  | 提供OpenAI、Anthropic、DeepSeek、Gemini等大模型高质量免费llmapi，纯官转api，非逆向，可用于日常开发测试、并发测试、日常办公等场景
lov0u/freellmapi | 32* | mit | pushed 2026-07-30 |  | 
yawo/freellmapi-proxy | 26* | mit | pushed 2026-05-05 |  | Free LLM proxy forked from https://github.com/tashfeenahmed/freellmapi
nglmercer/freellmapiV2 | 20* | mit | pushed 2026-11-01 |  | One OpenAI-compatible endpoint.

### named-anythingllm  ::  anythingllm
Mintplex-Labs/anything-llm | 67943* | mit | pushed 2026-11-04 |  | Stop renting your intelligence. Own it with AnythingLLM. Everything you need for a powerful local-first agent 
ArvinLovegood/go-stock | 8052* | gpl-3.0 | pushed 2026-11-03 |  | 🦄🦄🦄AI赋能股票分析：AI加持的股票分析/选股工具。股票行情获取，AI热点资讯分析，AI资金/财务分析，涨跌报警推送。�
techjarves/Portable-AI-USB | 2278* | mit | pushed 2026-07-04 | ARCHIVED | A 100% offline, fully portable, zero-trace AI (Ollama + Llama 3 + AnythingLLM) that runs natively from a USB d
travisvn/chatterbox-tts-api | 692* | agpl-3.0 | pushed 2025-12-23 |  | Local, OpenAI-compatible text-to-speech (TTS) API using Chatterbox, enabling users to generate voice cloned sp
Mintplex-Labs/anythingllm-docs | 431* | mit | pushed 2026-11-03 |  | Documentation of AnythingLLM by Mintplex Labs Inc.
Mintplex-Labs/anythingllm-extension | 234* | mit | pushed 2026-10-24 |  | Browser extension for AnythingLLM Docker & Desktop application

### littlecoder  ::  little-coder
ringhyacinth/Star-Office-UI | 7555* | other | pushed 2026-03-11 |  | A pixel office for your OpenClaw: turn invisible work states into a cozy little space with characters, daily n
itayinbarr/little-coder | 2714* | apache-2.0 | pushed 2026-09-18 |  | A harness optimized to smaller LLMs
TIGERB/easy-tips | 2709* |  | pushed 2025-12-27 |  | A little Tips in my Code Career with Go&PHP 🥳🥳🥳
dntzhang/pasition | 1207* |  | pushed 2023-05-27 |  | Path Transition with little JS code, render to anywhere - 轻量级 Path 过渡库，渲染到任何地方
romannurik/SlidesCodeHighlighter | 1122* | apache-2.0 | pushed 2026-04-09 |  | A little web app that helps you copy+paste syntax-highlighted code into slide decks.

### evalharness  ::  local-llm-coding-eval
gauravvij/local-llm-coding-eval | 8* |  | pushed 2026-05-06 |  | An eval harness and report on some of the latest LLMs that can be run locally
TreeTraceTool/TreeTrace | 3* | apache-2.0 | pushed 2026-09-02 |  | Catch your AI coding agent's security slips and turn the correction into a local regression eval. Local-first,
unravel1020/codebase-agent | 3* |  | pushed 2026-09-23 |  | LLM agent for local code repository analysis: LangChain tool calling + FAISS RAG + structured output + evals (
lastonoga/AQVEN | 3* | other | pushed 2026-11-04 |  | Python framework + local Studio for reliable LLM workflows: typed files in your repo, pre-run checks, experime
jovempedr0/GraphRAG-MAL | 3* |  | pushed 2026-10-05 |  | Anime & manga recommendation agent over a Neo4j knowledge graph built from MyAnimeList. Local LLMs (gpt-oss-20

### smallagent  ::  small local models coding agent scaffold
PDgit12/harnage | 2* | other | pushed 2026-07-30 |  | Prompt-to-harness builder: describe an agent harness, get a fully-owned Claude Code-level TS/Bun harness. A go

### gbnf  ::  grammar constrained generation tool calls local models

### winsb  ::  windows sandbox wsb agent execute

### sbwin  ::  sandbox windows restricted token
lhai36366/lhai36366 | 24* | apache-2.0 | pushed 2025-02-22 |  | WPF Partial Trust Security Article 10 minutes to read In general, Internet applications should be restricted f
slientmo/dsh-pwsh-unconfined | 1* | mit | pushed 2026-10-27 |  | DeepSeek Harness plugin: keep the pwsh tool usable on Windows when the ACL restricted-token sandbox runner fai
yoke233/yj-sandbox | 0* | apache-2.0 | pushed 2026-10-15 |  | Non-elevated Windows restricted-token sandbox (vendored & decoupled from openai/codex)
yzyyohh/dsh-windows-sandbox-0xc0000142 | 0* | mit | pushed 2026-09-15 |  | Reproducible measurement: a Windows restricted-token (WRITE_RESTRICTED) sandbox cannot spawn native children w
veypi/vbox | 0* | mit | pushed 2026-10-26 |  | Cross-platform process sandbox for Go: an ordered rule table decides, macOS Seatbelt / Linux bubblewrap / Wind
PHPCraftdream/wuserbox | 0* | other | pushed 2026-09-24 |  | Windows sandbox for AI coding agents: reads everything you can read, writes only where you allow, enforced by 

### sandboxie  ::  sandboxie
sandboxie-plus/Sandboxie | 19872* | gpl-3.0 | pushed 2026-11-04 |  | Sandboxie Plus & Classic
sandboxie/sandboxie | 3626* | gpl-3.0 | pushed 2022-09-22 |  | The Sandboxie application
KiExitDispatcher/GoDefender | 854* | other | pushed 2025-12-10 | ARCHIVED | Anti Virtulization, Anti Debugging, AntiVM, Anti Virtual Machine, Anti Debug, Anti Sandboxie, Anti Sandbox, VM
AlicanAkyol/sems | 463* |  | pushed 2018-11-22 |  | Virtualbox, VirtualMachine, Cuckoo, Anubis, ThreatExpert, Sandboxie, QEMU, Analysis Tools Detection Tools

```

## Appendix B. Direct lookups of well-known projects
```
anomalyco/opencode | 224584* | mit | 2026-11-04
ollama/ollama | 185932* | mit | 2026-11-04
ggml-org/llama.cpp | 133382* | mit | 2026-11-04
openai/codex | 133182* | apache-2.0 | 2026-11-04
OpenHands/OpenHands | 92659* | mit | 2026-11-04
cline/cline | 71313* | apache-2.0 | 2026-11-04
BerriAI/litellm | 62715* | other | 2026-11-04
microsoft/autogen | 61704* | cc-by-4.0 | 2026-10-28
mudler/LocalAI | 50205* | mit | 2026-11-04
Aider-AI/aider | 49946* | apache-2.0 | 2026-05-22
janhq/jan | 45452* | other | 2026-11-04
langchain-ai/langgraph | 44470* | mit | 2026-11-04
continuedev/continue | 36403* | apache-2.0 | 2026-11-04
huggingface/smolagents | 30216* | apache-2.0 | 2026-11-03
RooCodeInc/Roo-Code | 24249* | apache-2.0 | 2026-05-15 | ARCHIVED
SWE-agent/SWE-agent | 20724* | mit | 2026-11-02
flet-dev/flet | 17509* | apache-2.0 | 2026-11-04
Nuitka/Nuitka | 15225* | agpl-3.0 | 2026-11-04
pyinstaller/pyinstaller | 13139* | other | 2026-11-01
SWE-agent/mini-swe-agent | 9087* | mit | 2026-11-02
lm-sys/RouteLLM | 5675* | apache-2.0 | 2024-08-10 (stale)
beeware/briefcase | 3376* | bsd-3-clause | 2026-11-03
kivy/buildozer | 2046* | mit | 2026-11-02
```
