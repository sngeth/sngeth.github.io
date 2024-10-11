---
layout: post
title: "Using git checkout -"
category: "Git"
comments: true
---

As a developer, you often switch between branches or commits while working on multiple tasks, testing out code, or reviewing changes. One handy Git command that can help speed up this process is `git checkout -`. This command acts like a toggle, letting you jump back and forth between your current branch or commit and the last one you were on. Let’s explore a good use case for this feature and why it can be so useful in your daily workflow.

## What is `git checkout -`?

In Git, `git checkout -` is shorthand for checking out the **previously checked-out reference**, whether that reference is a branch, commit, or tag. It allows you to quickly toggle between your current location and the one you just left, no matter if it's a branch or a specific commit.

### Example Scenario: Reviewing and Hotfixing

Let’s say you're working on a feature branch, `feature/new-onboarding-flow`, and you're in the middle of implementing some new functionality. Suddenly, you receive an urgent request to fix a bug in production.

Here’s how `git checkout -` can come in handy:

### Step 1: Switch to the `main` Branch for the Hotfix

You need to fix the bug, so you quickly switch from your feature branch to the `main` branch:
```bash
git checkout main
```
Now you're on the `main` branch, where you can apply the necessary hotfix.

### Step 2: Make the Hotfix and Push the Changes

You make the changes, commit the fix, and push it to the remote repository:
```bash
git commit -m "Fix critical bug in production"
git push origin main
```

### Step 3: Switch Back to Your Feature Branch

After the fix is done, you want to quickly get back to working on your feature. Instead of typing the branch name again or checking the logs for where you were, you can simply run:
```bash
git checkout -
```

This command takes you back to the `feature/new-onboarding-flow` branch where you left off, allowing you to continue right where you were without extra steps.

### Step 4: Toggle Back Again

Need to check something else on the `main` branch again? Just run `git checkout -` once more to toggle back, and you’re instantly switched to `main`.

### Handling Uncommitted Changes

While `git checkout -` is a powerful shortcut, you need to be mindful of uncommitted changes when using it. If you have uncommitted changes, Git will do one of two things:

- **If there are no conflicts**: Git will apply your uncommitted changes when switching between branches or commits. This can be convenient when you want to keep working on something across branches.

- **If there are conflicts**: Git will prevent the switch and display an error message like:
   ```bash
   error: Your local changes to the following files would be overwritten by checkout:
           <file-name>
   Please commit your changes or stash them before you switch branches.
   ```

In this case, you’ll need to either commit your changes, discard them, or stash them using `git stash`.

### Using `git stash` to Save Uncommitted Changes

If you want to switch branches without losing your current work, you can use `git stash` to temporarily save your uncommitted changes, then switch branches, and later reapply the changes.

Here’s how to do it:
```bash
git stash           # save your uncommitted changes
git checkout -      # switch back to the previous branch
git stash pop       # reapply your changes
```

This workflow ensures that you can quickly move between branches or commits without losing your in-progress work.

### Toggling Between Branches and Commits

Let’s say before fixing the bug, you briefly switched to an older commit to test some behavior:
```bash
git checkout <commit-hash>
```
After testing the old commit, running `git checkout -` will take you right back to the branch you were working on. This flexibility to switch between branches and specific commits makes `git checkout -` particularly useful during testing or debugging sessions.

## Why Use `git checkout -`?

### 1. **Speed**:
When you’re working on multiple branches or need to switch between a branch and a specific commit, typing `git checkout -` is much faster than remembering the branch name or commit hash.

### 2. **Convenience**:
If you frequently switch between a feature branch and the `main` or `develop` branch, or between a commit and your branch, `git checkout -` saves you from having to repeat the full checkout commands.

### 3. **Simplicity**:
For quick, temporary switches (such as testing a fix, reviewing a commit, or updating something on a different branch), you can toggle back and forth without cluttering your workflow or history. You just need to remember to use `git stash` if you have uncommitted changes that might cause conflicts.

## Additional Tips

- You can combine `git checkout -` with other Git commands like `git rebase` or `git merge` if you frequently move between branches during development.

- This command is context-aware, meaning it works whether you last checked out a branch, commit, or even tag. It simply returns you to where you came from.

---
