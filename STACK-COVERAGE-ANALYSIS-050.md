# Does the "token-saving stack" research cover ADM's requirements? (ADM-050)

Source reviewed: owner-supplied chat export from another assistant (`ai_model.docx`): token-reduction GitHub projects, then a proposed stack (LangGraph + OpenCode + Codex CLI + Ollama/Jan/Edge0 + LiteLLM + RTK + SWE-ReX), plus the owner's rule "AI must be involved in every stage of development". The document is not stored in this repo.

## Owner decisions recorded in this session
- **AI source policy: local first, then genuinely free cloud tiers. Never paid.** (Rejects Codex subscription / paid-API escalation.) Caveat: ADM cannot prove a key is "free"; keys must come from accounts with no billing attached.
- Standing rule: AI participates in every development stage; deterministic tools (compilers, tests, linters) still run, and failed tests always block acceptance.
- Open (no answer yet): "no artificial stopping after N attempts". Default kept: bounded loop that escalates to another approach, then to a documented blocker.

## Facts checked (web, Nov 2026)
- Edge0 is real: Apache-2.0, SSD-streamed MoE, Windows C++/Vulkan engine open-sourced 2026-09-30. Headline result (35B model, ~3 GiB active memory, ~20 tok/s) was measured on a 24 GB Apple machine; no Windows/Intel numbers found. Models are "preview".
- Jan: OpenAI-compatible local server at `127.0.0.1:1337/v1`, llama.cpp engine; AGPLv3 (talk to it over HTTP; do not embed its code).
- SWE-ReX: a runtime interface. Backends are local shell, Docker, AWS, Modal, Fargate. The local backend is NOT isolation. OpenHands: sandbox is Docker; its docs say Windows is supported via WSL2.
- Not checked: RTK, Headroom, jCodeMunch, SQZ, Compaction, LLMLingua savings numbers (vendor claims), LangGraph checkpoint behaviour, Edge0 coding quality.

## Coverage of ADM requirements
| # | Requirement | In the document? | ADM today |
|---|---|---|---|
| 1 | One Windows app, plain-language request, visible progress | No (CLI tools; Jan is a chat app) | Window exists; cannot take a request |
| 2 | Local free AI on 16/32 GB | Yes (Ollama, Jan, Edge0), unmeasured on your hardware | Ollama only; first-run download prompt added |
| 3 | No paid tokens, no app switching | Conflicts (Codex, paid APIs, many tools) | Local only |
| 4 | Plan, code, test, repair, regress; build EXE / APK / web | Partly (agent loop, QA gates); builds not covered | Repair loop only |
| 5 | Durable state, crash/reboot/context recovery | Claimed via LangGraph (unverified) | Own queue + journal; unit-tested, Windows reboot untested |
| 6 | Isolation of generated code | **No on a plain PC**: needs Docker + WSL2 or paid cloud | None (critical gap) |
| 7 | Audit-grade evidence | Principles match ADM's | Partly implemented |
| 8 | Real-model and packaged end-to-end tests | Benchmark ideas only | Fake-model packaged test only |
| 9 | Friendly errors, simple install, model provisioning | No (developer PowerShell: npm, uv, pip) | First-run prompt built, untested for real |
| 10 | Cumulative ZIP + handoff each release | n/a | Done |
| 11 | AI at every stage (requirements, architecture, review, security, QA) | Described as roles; nothing built | AI only writes patches |

## What to take from it
- Use as **reference, not dependency**: ADM must stay one self-contained app. Ideas worth borrowing: keep full logs on disk and show the model only the failing excerpt; repo/symbol map so small-context models see only relevant code; checkpointed lifecycle states; independent review pass.
- Token-saving tools mainly help cloud/subscription agents. ADM's local models have no token bill but a small context window (now pinned at 8192), so context budgeting matters more than compression proxies.
- Add backend choice: any local OpenAI-compatible server (Jan, llama.cpp, LM Studio) besides Ollama. Edge0 only after benchmarking on the owner's PC.
- Sandbox: do not adopt Docker-based tools. Evaluate native Windows options (Job Object + restricted token / AppContainer; Windows Sandbox on Pro/Enterprise).
- Small local models must not be the final approver; deterministic test evidence stays the release gate.
