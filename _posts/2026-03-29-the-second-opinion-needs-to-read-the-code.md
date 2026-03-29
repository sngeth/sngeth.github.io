---
layout: post
title: "the second opinion needs to read the code"
date: 2026-03-29
categories: llm agents code-review swe-bench research
excerpt: "when GPT critiques Claude's patches without seeing the repo, the revised patches pass fewer tests. when GPT has the same tools and repo access, it fixes bugs Claude missed. the capability asymmetry was the problem, not cross-model review."
---

---

- [the premise](#the-premise)
- [the experiment](#the-experiment)
- [run 1: the reviewer can't read the code](#run-1-the-reviewer-cant-read-the-code)
- [run 2: the reviewer gets equal tools](#run-2-the-reviewer-gets-equal-tools)
- [what changed](#what-changed)
- [what the literature missed](#what-the-literature-missed)
- [what this means](#what-this-means)

---

## the premise

developers get stuck in single-model ruts. you ask Claude to fix a bug, rephrase three times, get variations of the same wrong answer. so you switch to GPT. different perspective, maybe better.

this works often enough that developers keep doing it. so i asked: what if the second model explicitly reviewed the first model's fix and pointed out what's wrong, then the first model revised? i built this and tested it with ground truth -- SWE-bench tasks where the patches either pass the test suite or they don't.

the first result was clear: the critique made things worse. then i gave the reviewer actual tools, and the result flipped.

## the experiment

30 tasks from SWE-bench Lite -- real GitHub issues across 10 Python repositories. Claude Opus 4.6 fixes the bug with full agentic repo access (file browsing, code search, shell execution via the Claude Agent SDK). three patches per task:

**v1 -- solo.** Claude fixes the bug alone. no review.

**v2 -- cross-model review.** GPT-5.4 critiques Claude's fix. Claude reads the critique, gets a fresh copy of the repo, and revises.

**v3 -- self-review.** Claude critiques its own fix, then revises on a fresh copy.

same author model, same repo access, same task. one variable: who wrote the critique. all three patches run through SWE-bench's test harness. pass or fail. no judgment calls.

### the flow

each agent runs in an isolated Docker container with the target repo mounted. Claude uses the [Claude Agent SDK](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/sdk) (Claude Code) with full agentic tools — file read/write, bash, grep, code search. in run 2, GPT uses [OpenAI Codex CLI](https://github.com/openai/codex) with equivalent capabilities. in run 1, GPT runs bare chat completions with no tools.

for each task, the flow is:

1. **Claude solo** — gets the issue description and the repo. explores the codebase, finds the bug, edits the files. the `git diff` of the modified repo is patch v1.
2. **GPT critique** — gets the issue description, Claude's full response (reasoning + code changes), and in run 2, the repo. produces its own analysis of the problem and a critique of Claude's approach.
3. **Claude revision** — gets the issue description, its own original response, GPT's critique, and a *fresh* copy of the repo (no edits from step 1). reads the critique and applies a revised fix. the diff is patch v2.
4. **Claude self-critique** — same as step 2 but Claude critiques its own step 1 response.
5. **Claude self-revision** — same as step 3 but using the self-critique. the diff is patch v3.

the fresh repo copy in steps 3 and 5 matters — Claude isn't editing on top of its previous fix. it starts clean and applies the revision from scratch. this means if the critique says "your approach is wrong, do X instead," Claude can take a completely different approach.

i ran this twice. the only difference: how much access GPT had in step 2.

## run 1: the reviewer can't read the code

GPT-5.4 runs as bare chat completions. no repo access, no file browsing, no shell. it sees Claude's explanation of its fix -- the reasoning and code snippets -- but can't read the actual source files or verify its claims against real code.

| condition | passed | failed | error | pass rate |
|-----------|--------|--------|-------|-----------|
| solo (v1) | 16 | 10 | 4 | **53%** |
| self-review (v3) | 14 | 8 | 8 | **47%** |
| cross-review (v2) | 10 | 12 | 8 | **33%** |

| outcome | cross-review | self-review |
|---------|-------------|-------------|
| solo passed, review **broke** | 6 | 5 |
| solo missed, review **fixed** | 0 | 3 |
| net | **-6** | **-2** |

cross-model review broke 6 working patches and fixed zero. purely destructive.

the critiques sounded authoritative. GPT identified "issues" that were specific, technical, and plausible:

- "your fix only handles the forward migration, you missed the backward direction"
- "booleans are categorical, not continuous -- casting to float is wrong"
- "your change targets code that doesn't exist in the actual module structure"

some of these were correct observations. some were hallucinated. [studies of LLM-generated code reviews](https://arxiv.org/abs/2508.08661) found hallucinations in 43-47% of generated review comments on fine-tuned models -- input inconsistencies, logic contradictions, and intent deviations. frontier models likely hallucinate less, but the failure mode is the same: the review identifies problems that don't exist. Claude couldn't tell the difference. it found the critiques persuasive and revised its working fixes into broken ones.

models trained with RLHF learn to accommodate feedback. [Sharma et al. (2024)](https://arxiv.org/abs/2310.13548) showed this is a structural property: RLHF optimizes for user approval over truthfulness, and both humans and preference models prefer sycophantic responses over correct ones. GPT's critique has high perplexity from Claude's perspective -- unfamiliar reasoning patterns and vocabulary that read as *novelty* rather than *noise*. Claude interprets the foreign-sounding feedback as genuine outside perspective that deserves accommodation, even when the original fix was correct.

self-review (v3) was less destructive because Claude's own critique sounds familiar. it partially sees through its own doubts and is less compelled to act on them.

## run 2: the reviewer gets equal tools

GPT-5.4 runs OpenAI's [Codex CLI](https://github.com/openai/codex) -- the same class of agentic tool as Claude Code. full repo access, file browsing, shell execution, code search. when it critiques Claude's fix, it reads the actual files and verifies its claims against real code.

| condition | passed | failed | error | pass rate |
|-----------|--------|--------|-------|-----------|
| solo (v1) | 16 | 12 | 1 | **55%** |
| self-review (v3) | 16 | 8 | 3 | **59%** |
| cross-review (v2) | 15 | 8 | 4 | **56%** |

| outcome | cross-review | self-review |
|---------|-------------|-------------|
| solo passed, review **broke** | 5 | 4 |
| solo missed, review **fixed** | **4** | **4** |
| net | **-1** | **0** |

cross-model review still broke 5 tasks -- sycophancy doesn't disappear -- but it also **fixed 4 that solo couldn't solve**. the net dropped from -6 to -1. self-review was perfectly neutral: broke 4, fixed 4.

the tasks GPT's grounded critique fixed were bugs where Claude's solo approach was fundamentally wrong and GPT -- having read the actual code -- identified the correct direction.

## what changed

the critique quality. not the model, not the prompts, not the tasks. just whether the reviewer could read the code.

**ungrounded critique** (run 1): "your approach probably doesn't handle the backward migration." GPT reasons from Claude's description. it might be right, it might be hallucinating a problem that doesn't exist.

**grounded critique** (run 2): "i read the migration file at line 340 and the backward path already handles this case. your fix is correct but you should also add a test." GPT verified its claim against the code. the critique is specific, falsifiable, and anchored to a real file.

the sycophancy problem persists either way -- cross-review still broke 5 tasks in run 2. but grounded critique adds enough genuine signal to offset the losses. the reviewer catching real bugs compensates for the cases where the author over-accommodates.

## what the literature missed

the self-preference bias literature ([Panickssery et al., 2024](https://arxiv.org/abs/2410.21819); [Bavaresco et al., 2025](https://arxiv.org/abs/2508.06709)) measures bias in evaluation settings -- score two outputs side by side. they found models favor their own. in revision, i found the opposite: models defer to the other's critique. these are the same perplexity mechanism in different settings. familiar text gets preference in evaluation; unfamiliar critique gets deference in revision.

the [Rethinking Mixture-of-Agents](https://arxiv.org/abs/2502.00674) paper (2025) found that Self-MoA (same model, multiple runs) outperforms Mixed-MoA (different models). they attributed this to model quality. the data here suggests a different variable: tool access. GPT-5.4 and Claude Opus 4.6 trade leads depending on the benchmark -- Opus leads on SWE-bench Verified (80.8% vs ~80%), GPT-5.4 leads on the harder SWE-bench Pro (57.7% vs ~45%). neither is categorically weaker. but without repo access, GPT produces weaker critiques regardless of its model capability. the same model went from net -6 (no tools) to net -1 (equal tools) on the same tasks.

[industrial-scale code review research](https://arxiv.org/abs/2505.17928) identifies false alarm reduction as a key open challenge -- LLM reviewers produce redundant or hallucinated comments frequently enough to require multi-stage filtering before reaching developers. [analysis of iterative AI code generation](https://arxiv.org/abs/2506.11022) found that critical vulnerabilities increase across successive LLM-driven revision rounds, with statistically significant degradation after iteration 5 -- the feedback loop amplifies flaws rather than correcting them. [evaluations of Copilot's security review](https://arxiv.org/abs/2509.13650) found it frequently missed critical vulnerabilities while proposing insecure changes.

the production code review tools have already converged on this lesson. GitHub Copilot's code review [switched to an agentic architecture](https://github.blog/changelog/2026-03-05-copilot-code-review-now-runs-on-an-agentic-architecture/) in March 2026 — the reviewer now browses the full repo, reads cross-file dependencies, and gathers directory structure before commenting. earlier versions reviewed diffs without repo context and [produced enough false positives](https://github.blog/changelog/2025-10-28-new-public-preview-features-in-copilot-code-review-ai-reviews-that-see-the-full-picture/) that GitHub had to blend LLM review with deterministic tools like ESLint and CodeQL. CodeRabbit [spins up sandboxed environments per PR](https://cloud.google.com/blog/products/ai-machine-learning/how-coderabbit-built-its-ai-code-review-agent-with-google-cloud-run) with shell access, grep, and ast-grep — the reviewer runs analysis code against the actual codebase. both moved from reasoning-about-diffs to reading-the-repo for the same reason the data here shows: unverified review produces hallucinated critique.

none of this work compared the same reviewer with and without repo access on the same tasks using ground truth, or measured whether cross-model review is worse than self-review.

## what this means

**ungrounded review is worse than no review.** if the reviewer can't read the actual code, it hallucinates bugs, and the author accommodates the hallucinations. this applies to any workflow where a model critiques code it can't see -- including pasting snippets into a chat window and asking "what's wrong with this."

**grounded review is net -1.** when the reviewer has the same tools as the author, it breaks about as many things as it fixes. the value is in catching bugs the author can't see -- a different model with different reasoning patterns identifies failure modes the author's model is blind to.

**self-review is the safest option.** Claude reviewing its own work was net zero in both runs. the model partially sees through its own doubts, making it less prone to false positive accommodation.

**the reviewer needs to verify its claims.** in human code review, the reviewer reads the actual code before commenting. in AI code review, the reviewer needs the same repo access so it can check whether its objections are real before raising them. a reviewer that can't verify its own claims produces hallucinated critiques that the author model treats as authoritative.

**switching models when stuck is the same dynamic.** when you switch from Claude to GPT in OpenCode or similar tools, GPT sees the full conversation history including the prior model's failed fix. switching to GPT and reading its perspective yourself is fine -- you're the filter. the risk is switching back and letting Claude revise based on GPT's feedback without scrutiny. if GPT has full agentic access to the repo, its feedback is more likely to be grounded. if it's just a chat window, it's run 1.

**don't auto-apply review suggestions.** cross-model critique is valuable when a human reads it and decides whether to act. the problem is when the critique feeds back into the author model automatically. the model can't distinguish a valid objection from a confident hallucination, so it accommodates both.

---

## experimental details

**system.** Claude Opus 4.6 runs in Docker with the Claude Agent SDK -- file I/O, bash, web search, code editing. GPT-5.4 runs either bare chat completions (run 1) or [OpenAI Codex CLI](https://github.com/openai/codex) (run 2) with equivalent agentic capabilities.

**tasks.** 30 from [SWE-bench Lite](https://www.swebench.com/lite.html), 3 per repository across 10 Python projects.

**verification.** SWE-bench's Docker-based test harness. each patch is applied to the repo at the base commit and tested against the task's test suite. pass/fail.

**prior bias runs.** before ground truth, three runs measured whether the orchestrator (Claude judging Claude vs GPT disagreements) showed self-preference bias. none did -- the orchestrator selected GPT's position 50-52% across all conditions (Sonnet orchestrator, Opus orchestrator, and Opus without critiques).

**limitations.** n=30. no test-feedback loop (agents get one session to explore and fix, no iterative debugging against test results). results may differ with different models, different tasks, or different critique prompts.

---
