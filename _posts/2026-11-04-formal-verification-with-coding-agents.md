---
layout: post
title: "formal verification with coding agents"
date: 2026-11-04
categories: ["Software Development", "AI"]
excerpt: "Notes from Superlinear, plus a PodSummary quota example: reproducing two historical races with Z3 and checking the connection to real code."
comments: true
---

These are some notes from Superlinear's episode [Coding Agents Just Changed Formal Verification Forever](https://www.youtube.com/watch?v=yex-Xq0_orw), published October 29, 2026. The discussion covers using coding agents to write specifications, run verification tools, and fix the bugs those tools find.

The discussion uses reversing a string as a simple example. We can test specific inputs or use property-based tests to generate many inputs. With formal verification, we start with a specification and try to prove a property within its stated scope.

Here's the property we want to check:

```javascript
reverse(reverse(value)) === value
```

Reversing `"hello"` twice should give us `"hello"`. But the property alone doesn't mean the code actually reverses it. Consider this implementation:

```javascript
function reverse(value) {
  return value;
}
```

This does not reverse anything. It returns the input unchanged. The property passes, but the code is incorrect.

The verifier could correctly prove this property. We need a specification that also describes the required order of the characters.

This matters when an agent writes both the implementation and the property. A passing check is useful only if the property describes the behavior we need.

Consider a refund system. With tools like TLA+ and Quint, we can model it as a state machine: pending, completed, or failed. We might check that the same payment cannot receive two successful refunds.

The result applies to the model. We still need to establish that the implementation follows it, including how it handles retries and concurrent requests. An agent could change the implementation while leaving the model alone, and the model check would still pass.

Model-based tests and checks against execution traces can help us find that difference. Running an unchanged model again doesn't establish that the new code follows it. When the covered code changes, we need to review whether the model still describes it.

We also need to know what kind of check ran. A bounded model check covers its configured limits. For example, [Quint's Apalache backend](https://github.com/quint-co/quint/blob/main/docs/content/docs/model-checkers.mdx) checks executions up to a specified number of steps. A passing result does not establish that the property holds beyond that bound.

We also need explicit assumptions. To show that a user never stays in a loading state, we need to account for timeouts and scheduling. We can't assume a database or API will always respond.

The episode introduces Poteto's [`/create-formal-verification-skill`](https://github.com/cursor/plugins/blob/main/pstack/skills/create-formal-verification-skill/SKILL.md) in the official [pstack plugin](https://github.com/cursor/plugins/tree/main/pstack). With pstack installed in Cursor, you can run:

```text
/create-formal-verification-skill
```

You can let it inspect the repository for a useful target, or name the behavior you want checked. For the hypothetical refund example, you could write:

```text
Check whether concurrent requests or retries can issue two successful
refunds for the same payment. State the assumptions and show a failing
event sequence if the rule can be broken.
```

The skill starts from the code and looks for a rule whose failure would harm users and whose failing cases are hard to reach with ordinary tests. It then chooses a suitable tool. Event ordering may call for a model checker. A property about executable code may need a verifier that supports the language.

A useful requirement is to show that the check can fail. We deliberately break the implementation, for example by removing a guard or reordering a step, and check that verification detects it. Otherwise, a passing check could hide an incomplete model or a property that never encounters the relevant condition.

The output is a project-local verification skill. It records the covered code, assumptions, bounds, a repeatable command, and the commit where the connection to the implementation was last confirmed. Before handoff, the agent must try the generated skill against a scratch regression in the real code and then remove that scratch change. The recorded commit is evidence of a review, not proof that the model and implementation agree.

Future changes still need that connection checked. If the current code violates the property, the skill calls for reporting the counterexample rather than weakening the check or silently changing product code. This gives the next agent a specific rule and procedure to maintain.

I tried this workflow on the commit history of [PodSummary](https://podsummary.io), my podcast app. I asked the agent to find a bug fix that formal verification could have exposed earlier. It selected two related bugs in the summary allowance code. Both had already been fixed, so this was a retrospective check.

The first bug was a race between requests. A Free account had an allowance of five summaries. The code checked usage before processing and incremented it afterward. That allowed this sequence:

1. The account has used four summaries.
2. Request A reads four and passes the check.
3. Request B also reads four and passes the check.
4. A finishes and increments the count to five.
5. B finishes and increments it to six.

The first fix allowed the increment only while the count was below the limit. But resetting the allowance remained a separate operation. Several requests could read the same expired reset date. A could reset the count and claim a slot, then B could reset the count again. A's claim disappeared from the stored usage.

The later fix combined the reset, limit check, and increment into one atomic database update. Another request could no longer insert a reset between those steps.

The agent chose [Z3](https://github.com/Z3Prover/z3), an SMT solver, based on the property we wanted to check. The skill did not prescribe Z3. We used it to model these operations and ask whether any sequence within the bounds could break either of two rules:

- Successful claims plus prior usage must not exceed the allowance.
- After a reset, the stored count must preserve all usage in the current period.

We needed both rules. A counter that accurately records six claims still violates a limit of five. A counter that erases a claim can remain below five while allowing too much work. Checking only one rule would miss part of the problem.

Z3 found counterexamples for both historical designs. The current atomic-update model passed both checks within six requests and twelve transitions. The model assumed one account, a fixed time and tier, valid stored values, and no other code changing the counter. It did not cover time advancing, tier changes, refunds, or every summary-access path. This was a bounded check of a separate model, not a proof of the TypeScript application.

We then ran eleven existing integration tests against the real helper and local Postgres. All passed. For the skill's handoff check, the agent copied the repository into a temporary directory and deliberately bypassed the SQL quota guard. Nine tests failed. After restoring the guard, all eleven passed again.

This exposed the model-to-code gap. The unchanged model still passed while the modified implementation failed its database tests. The generated verification command runs both checks. When the code changes, someone still needs to review whether the model describes it. These integration tests do not prove that connection for every execution.

The result was a project-local `verify-summary-quota` skill that records the properties, assumptions, bounds, covered code, and a repeatable command. The check reproduced historical bugs that ordinary sequential requests could miss. We did not discover or fix a new production bug in this run.

Brandon also explores using the same state-machine representation for execution and verification. That could reduce the amount of separate logic we need to maintain. Some tools already verify executable programs more directly; [Dafny](https://dafny.org/dafny/DafnyRef/DafnyRef.html) supports both verification and compilation. Building a new checker ourselves would introduce another piece of software whose correctness we need to establish.

There are substantial results behind this discussion. [Anthropic reported proofs for 239 entry points across 123 open-source libraries](https://www.anthropic.com/research/formal-verification). These established specific no-crash properties for compiled RISC-V programs under stated input, memory, and operating-system assumptions. They did not establish that every library was free of every bug.

For an existing application, I would start with a small rule where a failure matters. State the property and assumptions, use an established tool, and check how the result connects to the implementation. If the tool finds a counterexample, keep that input or event sequence and add a regression test where appropriate.

We still need tests and review. Formal verification gives us another way to check a specific requirement, provided we understand what the result covers and which assumptions it needs.
