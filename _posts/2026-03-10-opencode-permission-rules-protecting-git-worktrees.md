---
layout: post
title: "opencode permission rules: protecting your code from ai agents"
date: 2026-03-10
categories: opencode ai git worktrees terraform
---

## a terraform destroy that wiped production

in february 2026, alexey grigorev [let his claude code agent run `terraform destroy`](https://alexeyondata.substack.com/p/how-i-dropped-our-production-database) on what he thought were duplicate resources. the agent had silently unpacked an old terraform state file that pointed at production infrastructure instead. the entire course management platform for datatalks.club went down -- database, vpc, ecs cluster, load balancers, bastion host, all gone. every automated snapshot was deleted with it.

> "i over-relied on the ai agent to run terraform commands. i treated `plan`, `apply`, and `destroy` as something that could be delegated. that removed the last safety layer."

the agent told him it would run `terraform destroy`. he approved it. the permission system worked -- it asked. but he didn't realize the state file had changed underneath him, so "yes, destroy those duplicates" actually meant "yes, destroy production."

this is the hard lesson: **`ask` only protects you if you understand what you're approving.** he saw `terraform destroy` and it looked logical in context. the agent had even explained its reasoning. but the premise was wrong because the state file was wrong, and no amount of prompting catches that.

> "what happened was that i didn't notice claude unpacking my terraform archive. it replaced my current state file with an older one that had all the info about the datatalks.club course management platform."

his fix was to stop delegating entirely:

> "agents no longer execute commands. every plan is reviewed manually. every destructive action is run by me."

that works, but it's also the nuclear option. opencode's permission system offers a middle ground: let agents run safe commands freely, prompt you for risky ones, and hard-block the ones where no amount of context makes them safe to delegate.

the same class of problem applies to git worktrees. an agent running `git restore`, `git reset --hard`, or `git clean` can silently wipe uncommitted changes with no recovery path. here's a practical config that draws the line.

## the configuration

add this to your `~/.config/opencode/opencode.json`:

```json
{
  "permission": {
    "bash": {
      "*": "ask",
      "git status*": "allow",
      "git diff*": "allow",
      "git log*": "allow",
      "git add*": "allow",
      "git commit*": "ask",
      "git stash*": "ask",
      "git checkout*": "ask",
      "git restore*": "ask",
      "git reset*": "ask",
      "git clean*": "deny",
      "git worktree*": "ask"
    }
  }
}
```

### how it works

opencode evaluates permission rules using **last-match-wins** ordering. the `"*": "ask"` catch-all at the top means any bash command not explicitly listed requires your approval. more specific rules below it override the default for their matched patterns.

three permission levels:

- **`allow`** -- runs silently, no prompt
- **`ask`** -- prompts you with once/always/reject before executing
- **`deny`** -- blocked outright, the agent cannot run it at all

## test results

all tests run against a stub git repo with uncommitted modifications and untracked files present.

### "allow" commands -- ran without prompting

these are safe, read-only (or low-risk staging) operations. the agent runs them freely.

#### test 1: `git status`

**rule:** `"git status*": "allow"` | **result:** executed immediately, no prompt.

```
$ git status
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   main.py

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	untracked-work.txt

no changes added to commit (use "git add" and/or "git commit -a")
```

#### test 2: `git diff`

**rule:** `"git diff*": "allow"` | **result:** executed immediately, no prompt.

```
$ git diff
diff --git a/main.py b/main.py
index 110c807..11a6bc3 100644
--- a/main.py
+++ b/main.py
@@ -4,3 +4,7 @@ def greet(name):

 if __name__ == "__main__":
     print(greet("world"))
+
+
+def farewell(name):
+    return f"Goodbye, {name}!"
```

#### test 3: `git log`

**rule:** `"git log*": "allow"` | **result:** executed immediately, no prompt.

```
$ git log --oneline
bf23d2b initial commit
```

#### test 4: `git add`

**rule:** `"git add*": "allow"` | **result:** executed immediately, no prompt.

```
$ git add .
(no output -- files staged successfully)
```

---

### "ask" commands -- prompted for approval

these commands can modify your working tree or history. opencode shows a prompt with **once**, **always**, or **reject** options before the command runs.

#### test 5: `git commit`

**rule:** `"git commit*": "ask"` | **result:** prompted, approved, then executed.

```
$ git commit -m "test commit from agent"
[main 7db8a3c] test commit from agent
 2 files changed, 6 insertions(+)
 create mode 100644 untracked-work.txt
```

#### test 6: `git stash`

**rule:** `"git stash*": "ask"` | **result:** prompted, approved, then executed.

```
$ git stash
Saved working directory and index state WIP on main: 7db8a3c test commit from agent
```

#### test 7: `git restore`

**rule:** `"git restore*": "ask"` | **result:** prompted, approved, then executed.

```
$ git restore main.py
(no output -- changes silently discarded)
```

> this is one of the most dangerous "quiet" commands. without the `ask` rule, an agent could silently discard your uncommitted modifications with zero output to indicate anything happened.

#### test 8: `git checkout`

**rule:** `"git checkout*": "ask"` | **result:** prompted, approved, then executed.

```
$ git checkout feature-branch
Switched to branch 'feature-branch'
```

#### test 9: `git reset --hard`

**rule:** `"git reset*": "ask"` | **result:** prompted, approved, then executed.

```
$ git reset --hard HEAD
HEAD is now at c44ce28 test commit from agent
```

> this catches the most destructive variant (`--hard`) which resets the index and working tree, throwing away all uncommitted changes.

#### test 10: `git worktree`

**rule:** `"git worktree*": "ask"` | **result:** prompted, approved, then executed.

```
$ git worktree add ../permission-test-wt main
Preparing worktree (checking out 'main')
HEAD is now at 7db8a3c test commit from agent
```

---

### "deny" command -- blocked entirely

#### test 11: `git clean -fd`

**rule:** `"git clean*": "deny"` | **result:** blocked. the agent received an error and the command never executed.

```
$ git clean -fd
Error: The user has specified a rule which prevents you from using
this specific tool call. Here are some of the relevant rules:
[
  {"permission":"*","pattern":"*","action":"allow"},
  {"permission":"bash","pattern":"*","action":"ask"},
  {"permission":"bash","pattern":"git status*","action":"allow"},
  {"permission":"bash","pattern":"git diff*","action":"allow"},
  {"permission":"bash","pattern":"git log*","action":"allow"},
  {"permission":"bash","pattern":"git add*","action":"allow"},
  {"permission":"bash","pattern":"git commit*","action":"ask"},
  {"permission":"bash","pattern":"git stash*","action":"ask"},
  {"permission":"bash","pattern":"git checkout*","action":"ask"},
  {"permission":"bash","pattern":"git restore*","action":"ask"},
  {"permission":"bash","pattern":"git reset*","action":"ask"},
  {"permission":"bash","pattern":"git clean*","action":"deny"},
  {"permission":"bash","pattern":"git worktree*","action":"ask"}
]
```

the untracked file (`expendable.txt`) survived:

```
$ ls expendable.txt
expendable.txt
```

> `git clean` is the only command set to `deny` because it permanently removes untracked files with no recovery path -- not even `git reflog` can help you. the `ask` tier at least gives you a chance to think; `deny` takes the option off the table entirely.

---

## why this matters for worktrees

when you use `git worktree` to run multiple agents in parallel on different branches, each worktree has its own working tree but shares the same `.git` directory. this creates a unique risk surface.

### commands that destroy work inside a worktree

1. **`git restore <file>`** -- the most common agent culprit. agents run this reflexively to "undo" a bad edit. it silently discards your modifications with zero output. you'd never know it happened.
2. **`git reset --hard`** -- agents reach for this when things get messy and they want a "clean slate." resets the index and working tree, all uncommitted changes gone.
3. **`git checkout <branch>`** -- if uncommitted changes conflict with the target branch, git overwrites your working tree files. agents switch branches casually.
4. **`git clean -fd`** -- deletes all untracked files permanently. new files that were never staged are gone with no recovery path, not even `git reflog`.

### worktree management commands that destroy work

the worktree management commands themselves are also dangerous:

1. **`git worktree remove <path>`** -- deletes the entire worktree directory. git refuses if there are uncommitted modifications, but agents will retry with `--force` when they hit the error, which bypasses the safety check and nukes everything.
2. **`git worktree remove --force <path>`** -- skips the dirty-tree check entirely. if an agent decides to "clean up" a worktree you're still working in, all uncommitted files in that worktree directory are gone.
3. **`git branch -D <branch>`** -- while not a worktree command, an agent in one worktree can delete a branch that's checked out in another worktree, leaving it in a broken state.

### shared state risks across worktrees

all worktrees share the same `.git` directory. an agent operating in one worktree can affect others:

- **`git gc --prune=now`** can clean up loose objects that other worktrees still reference
- **ref updates** (tags, branches) in one worktree are immediately visible to all others
- **`git stash`** in one worktree is accessible from all worktrees -- an agent could accidentally pop another worktree's stash

the `"*": "ask"` catch-all is critical. it means any command not explicitly listed -- `rm`, `curl`, `python`, whatever -- still requires your approval rather than running blind.

## applying this to terraform

the datatalks.club incident would have been prevented with:

```json
{
  "permission": {
    "bash": {
      "terraform plan*": "ask",
      "terraform apply*": "deny",
      "terraform destroy*": "deny",
      "terraform import*": "ask"
    }
  }
}
```

`deny` on `terraform apply` and `terraform destroy` forces you to run them yourself in a separate terminal where you see the full plan output and can verify which state file terraform is using. the agent can still generate plans and write config -- it just can't pull the trigger.

this wouldn't have helped if he'd rubber-stamped an `ask` prompt the same way he approved the agent's reasoning in chat. but `deny` removes the option entirely -- the agent physically cannot execute the command, no matter how logical its explanation sounds.

## additional recommendations

if you're using multiple worktrees in different directories, add `external_directory` rules to control cross-worktree access:

```json
{
  "permission": {
    "external_directory": {
      "~/Code/my-project-wt-*": "ask"
    }
  }
}
```

this ensures the agent in one worktree has to get your approval before touching files in another worktree that's outside the directory where you launched opencode.

## important notes

- **restart required:** permission changes in `opencode.json` take effect on the next opencode launch, not mid-session.
- **last-match-wins:** rules are evaluated in order and the last matching rule wins. put the `"*"` catch-all first, specific rules after.
- **wildcard behavior:** `*` matches zero or more of any character (including spaces). `"git status*"` matches both `git status` and `git status --porcelain`.
- **per-agent overrides:** you can set different permissions per agent in the `"agent"` config section. for example, a review-only agent could have `"edit": "deny"`.
- **"always" is session-only:** when opencode prompts you and you choose "always", that approval only lasts for the current session. it lives in memory, not on disk -- it does **not** update `opencode.json`. once you restart opencode, you'll be prompted again. if you want a permanent allow rule, add it to `opencode.json` yourself.
