---
layout: post
title: "adding vim keybindings to opencode's tui"
date: 2026-03-11
categories: opencode vim typescript solidjs tui
excerpt: "a deep dive into adding vim keybindings to opencode's terminal UI -- matching claude code's vim feature set with a pure TypeScript state machine, cross-referenced against neovim's C source."
---

---

- [the request](#the-request)
- [what claude code's vim mode actually supports](#what-claude-codes-vim-mode-actually-supports)
- [opencode's TUI architecture](#opencodes-tui-architecture)
- [the four-layer architecture](#the-four-layer-architecture)
- [cross-referencing against neovim's source](#cross-referencing-against-neovims-source)
- [full vim mode reference](#full-vim-mode-reference)
- [how to try it](#how-to-try-it)
- [files changed](#files-changed)
- [more gotchas (found after shipping)](#more-gotchas-found-after-shipping)
- [escape key routing during generation](#escape-key-routing-during-generation)

---

## the request

claude code shipped vim mode in late 2025. within days, opencode had two open issues asking for the same thing -- [#1764](https://github.com/sst/opencode/issues/1764) and [#11111](https://github.com/sst/opencode/issues/11111), the latter with 20+ comments and a fair amount of frustration from people who'd switched from claude code specifically to get an open-source alternative but then had to give up muscle memory every time they opened the prompt.

opencode is exactly that: an open-source alternative to claude code. same agentic AI coding concept, same terminal-first workflow, but the source is public and you can modify it. the TUI is built on SolidJS and `@opentui/core`, a terminal rendering framework. the prompt input is a `TextareaRenderable` widget that handles text, cursor position, and syntax highlighting via extmarks.

the goal was exact parity with claude code's vim feature set. not a subset where we skip the hard parts, not a superset where we add visual mode and count prefixes. whatever claude code supports, we support. whatever it doesn't, we don't. that constraint actually made the scope manageable.

## what claude code's vim mode actually supports

the official docs at `code.claude.com/docs/en/interactive-mode` list the full feature set. two modes only: NORMAL and INSERT. no visual mode, no command mode, no ex commands.

**mode switching:**

- `i` -- insert before cursor
- `I` -- insert at first non-blank of line
- `a` -- insert after cursor
- `A` -- insert at end of line
- `o` -- open new line below, enter insert mode
- `O` -- open new line above, enter insert mode
- `Esc` -- return to normal mode

**navigation:**

- `h/j/k/l` -- left/down/up/right
- `w/e/b` -- word motions
- `0/$` -- line start/end
- `^` -- first non-blank
- `gg/G` -- buffer start/end
- `f/F/t/T{char}` -- character search on current line
- `;/,` -- repeat last f/F/t/T forward/backward

**editing:**

- `x` -- delete character
- `dd/D` -- delete line / delete to end
- `d{motion}` -- delete with motion
- `cc/C` -- change line / change to end
- `c{motion}` -- change with motion
- `yy/Y` -- yank line
- `y{motion}` -- yank with motion
- `p/P` -- paste after/before
- `>>/<<` -- indent/dedent
- `J` -- join lines
- `.` -- repeat last change

**text objects** (used with d/c/y):

- `iw/aw` -- inner/around word
- `iW/aW` -- inner/around WORD (whitespace-delimited)
- `i"/a"` -- inner/around double quotes
- `i'/a'` -- inner/around single quotes
- `i(/a(` -- inner/around parentheses
- `i[/a[` -- inner/around square brackets
- `i{/a{` -- inner/around curly braces

**explicitly not supported:**

- no visual mode (v/V)
- no count prefixes (3j, 5dd)
- no undo/redo (u, Ctrl+R)
- no / search
- no r (replace char in place)

that's the spec. now let's look at the codebase we're modifying.

## opencode's TUI architecture

opencode is a monorepo. the TUI lives in `packages/opencode/`. the relevant source tree:

```
packages/opencode/src/
  config/
    tui-schema.ts          # Zod schema for tui.json
    tui.ts                 # config loading
  cli/cmd/tui/
    app.tsx                # root component, provider tree
    context/
      keybind.tsx          # keybind context (existing pattern we follow)
      vim.tsx              # NEW: vim context
    component/
      prompt/
        index.tsx          # ~1171 lines, the prompt component
        textarea-keybindings.ts  # maps keybinds to KeyBinding[]
    lib/
      vim-engine.ts        # NEW: pure TS state machine
```

if you're wondering "why is a terminal app using SolidJS" -- the JSX you see in opencode's source isn't React. it's the same angle-bracket syntax, but SolidJS compiles it into direct reactive wiring with no virtual DOM and no diffing. the rendering stack is:

**SolidJS** (reactive state) → **@opentui/solid** (binding layer) → **@opentui/core** (Zig-based terminal engine)

SolidJS manages signals and effects. `@opentui/solid` translates JSX elements like `<box>` and `<textarea>` into native renderables backed by `@opentui/core`, which is written in Zig. bun is just the JavaScript runtime; there's no browser, no electron, no DOM at any point.

the way Zig ends up rendering to your terminal is through bun's FFI (foreign function interface). `@opentui/core` ships a platform-specific shared library (`.dylib` on macOS, `.so` on Linux) compiled from Zig source. the TypeScript side calls into it via `bun:ffi` -- you can see this in the type definitions: `createRenderer` returns a `Pointer`, `render` takes a `Pointer`, everything crosses the FFI boundary as raw pointers and primitives. no serialization, no IPC, just direct function calls into native code.

on the TypeScript side, each renderable (`BoxRenderable`, `TextRenderable`, `TextareaRenderable`) holds a Yoga layout node -- that's Facebook's cross-platform flexbox engine. when you write `<box flexGrow={1} paddingLeft={2}>`, Solid creates a renderable with those layout properties set on its Yoga node. the layout tree is computed in JavaScript, but the actual painting happens in Zig.

the render loop looks roughly like this:

1. something changes -- a signal updates, text is typed, the terminal resizes
2. Yoga recomputes the layout tree (which nodes moved, which resized)
3. each renderable paints its content into an `OptimizedBuffer` -- a Zig-allocated character grid where each cell holds a character, foreground color, background color, and text attributes
4. the Zig renderer diffs the current buffer against the previous frame
5. only the cells that actually changed get written to stdout as ANSI escape codes -- cursor movement sequences to skip unchanged regions, SGR sequences for colors and styles, then the character data

step 4 is where the performance comes from. a full-screen terminal might be 200x50 = 10,000 cells. if you type one character in the prompt, maybe 20 cells change. the Zig renderer writes escape codes for those 20 cells and skips the other 9,980. this is the same approach that `tmux` and `neovim` use -- compute the minimal diff, emit the minimal escape sequences.

when a signal like `vim.mode` changes, only the one `<text>` node showing `-- INSERT --` updates. that update is a direct property mutation on the Zig-backed renderable, which marks those cells dirty for the next paint. nothing else in the tree re-evaluates. this is why SolidJS is a good fit for TUI work: its granular reactivity maps directly to granular terminal updates.

the terminal rendering framework is `@opentui/core` at v0.1.87. it provides `TextareaRenderable`, which is the core input widget. the interface you care about:

```typescript
interface TextareaRenderable {
  plainText: string; // current text content
  cursorOffset: number; // get/set cursor position (byte offset)
  setText(text: string): void; // replace entire content
  insertText(text: string): void; // insert at cursor
  clear(): void;
  extmarks: Extmark[]; // syntax highlighting regions
}
```

key flow for keyboard input: config in `tui-schema.ts` defines what keybinds are valid, `keybind.ts` parses them, `keybind.tsx` provides them via SolidJS context, and `textarea-keybindings.ts` maps them to `KeyBinding[]` objects that the textarea widget understands. the prompt component (`prompt/index.tsx`) has an `onKeyDown` handler that intercepts keys before they reach the textarea.

the context pattern throughout the codebase uses a `createSimpleContext` helper:

```typescript
// from keybind.tsx -- the pattern we follow
export const { use: useKeybind, provider: KeybindProvider } =
  createSimpleContext({
    name: "Keybind",
    init: () => {
      // ... setup logic
      return {
        /* context value */
      };
    },
  });
```

`createSimpleContext` returns a `{ provider, use }` pair. the provider wraps children and makes the context available. `use` is the hook that components call to access it. we follow this exact pattern for vim.

the implementation of `createSimpleContext` is straightforward -- it's a thin wrapper around SolidJS's `createContext` and `useContext`:

```typescript
// simplified from context/common.ts
export function createSimpleContext<T>(opts: {
  name: string
  init: () => T
}) {
  const Context = createContext<T | undefined>(undefined)

  function provider(props: { children: JSX.Element }) {
    const value = opts.init()
    return <Context.Provider value={value}>{props.children}</Context.Provider>
  }

  function use(): T {
    const ctx = useContext(Context)
    if (!ctx) throw new Error(`${opts.name} context not found`)
    return ctx
  }

  return { provider, use }
}
```

the provider tree in `app.tsx` is a nested stack of these providers. order matters -- a provider can only call `use` on contexts that are higher in the tree (already initialized). `VimProvider` reads from `TuiConfigProvider`, so it must be nested inside it:

```tsx
// app.tsx (simplified)
export function App() {
  return (
    <TuiConfigProvider>
      <ThemeProvider>
        <KeybindProvider>
          <VimProvider>
            {" "}
            {/* reads TuiConfig, provides vim context */}
            <Prompt />
          </VimProvider>
        </KeybindProvider>
      </ThemeProvider>
    </TuiConfigProvider>
  );
}
```

the actual tree has more providers, but this shows the nesting relationship. `Prompt` can call `useVim()`, `useKeybind()`, `useTheme()`, and `useTuiConfig()` because all four are ancestors in the tree.

## the four-layer architecture

the implementation splits across four layers. each layer has a single responsibility and doesn't reach into the others' concerns.

### layer 1: config

`packages/opencode/src/config/tui-schema.ts` defines the shape of `tui.json`. we add one field:

```typescript
vim: z.boolean()
  .optional()
  .describe("Enable vim editing mode in the prompt input");
```

opt-in via `{ "vim": true }` in `.opencode/tui.json`. defaults to false (or rather, undefined, which we treat as false).

we used `.optional()` instead of `.default(false)` deliberately. the `tui.ts` loader has several fallback paths that construct empty `{}` objects and merge them. with `.default(false)`, Zod's output type inference makes `vim` non-optional (`boolean` instead of `boolean | undefined`), which causes type errors at those empty-object fallback sites. `.optional()` keeps `vim` as `boolean | undefined` throughout, and we handle the `?? false` defaulting in the context layer where we actually use it.

### layer 2: VimEngine

`packages/opencode/src/cli/cmd/tui/lib/vim-engine.ts` is 957 lines of pure TypeScript. zero imports. no SolidJS, no `@opentui/core`, no external dependencies at all.

the public interface:

```typescript
export type VimMode = "normal" | "insert";

export interface VimKeyEvent {
  key: string;
  ctrl: boolean;
  shift: boolean;
  meta: boolean;
}

export interface VimResult {
  consumed: boolean;
  newText?: string;
  newCursor?: number;
  modeChange?: VimMode;
}

export class VimEngine {
  getMode(): VimMode;
  handleKey(event: VimKeyEvent, text: string, cursor: number): VimResult;
  reset(): void;
}
```

`handleKey` takes the current text and cursor position as arguments. it returns what changed. the engine never holds a reference to the textarea -- it doesn't know `TextareaRenderable` exists. the caller reads the current state, passes it in, and applies the result. this makes the engine testable with plain strings and integers, no UI framework required.

**internal state:**

```typescript
private mode: VimMode = "normal"
private pending: string = ""          // multi-key buffer: "d", "c", "y", "g", ">", "<", "f", "F", "t", "T"
private register: string = ""         // unnamed yank register
private lastChange: ChangeRecord | null = null   // for dot repeat
private lastFtMotion: FtMotion | null = null     // for ; and , repeat
private insertSession: InsertSession | null = null  // tracks text on insert entry
```

`pending` is how operator + motion composition works. pressing `d` doesn't immediately do anything -- it sets `pending = "d"` and returns `{ consumed: true }`. the next key press sees `pending === "d"` and knows to interpret the key as a motion. pressing `w` with `pending === "d"` triggers `applyOperator("d", text, cursor, "w")`.

`applyOperator` calls `getMotionRange` to find the affected character range, then deletes it and stores the deleted text in `register`. for the `c` operator, it also switches to insert mode after deleting. for `y`, it just stores the range in `register` without modifying text.

text objects (`iw`, `a"`, `i{`, etc.) go through `applyTextObjectOperator` instead, which calls `findTextObjectRange` to locate the object boundaries.

`lastChange` is a `ChangeRecord`:

```typescript
interface ChangeRecord {
  type: "operator-motion" | "operator-textobj" | "insert-change" | "simple";
  operator?: string;
  motion?: string;
  textobj?: string;
  insertedText?: string; // what was typed during the insert session
  simpleOp?: () => VimResult; // for x, dd, D, J, >>, <<
}
```

dot repeat replays whatever `lastChange` describes. for `dw`, it re-runs `applyOperator("d", text, cursor, "w")` against the current text and cursor. for `cw{text}Esc`, it re-runs the delete, switches to insert mode, inserts `insertedText`, then switches back to normal.

`insertSession` tracks the text content when we entered insert mode. on `Esc`, we diff the current text against `insertSession.textBefore` to find what was typed, and store that as `insertedText` in `lastChange`. this is how dot repeat knows what to re-insert.

`lastFtMotion` stores the last `f/F/t/T` operation:

```typescript
interface FtMotion {
  type: "f" | "F" | "t" | "T";
  char: string;
}
```

`;` replays it in the same direction. `,` replays it in the opposite direction (f becomes F, t becomes T, and vice versa).

**the key dispatch loop:**

```typescript
handleKey(event: VimKeyEvent, text: string, cursor: number): VimResult {
  if (this.mode === "insert") {
    if (event.key === "escape") {
      return this.enterNormal(text, cursor)
    }
    return { consumed: false }  // let the textarea handle it
  }

  // normal mode
  const key = this.resolveKey(event)  // normalize shift+key combos

  if (this.pending) {
    return this.handlePendingKey(key, text, cursor)
  }

  return this.handleNormalKey(key, text, cursor)
}
```

in insert mode, the engine only intercepts `Escape`. everything else returns `{ consumed: false }`, which tells the prompt component to let the key fall through to the textarea's normal handling. this is the key insight: vim mode doesn't replace the textarea's input handling, it wraps it. regular typing in insert mode goes through the existing path unchanged.

### layer 3: VimProvider

`packages/opencode/src/cli/cmd/tui/context/vim.tsx` is 35 lines:

```typescript
import { createSignal } from "solid-js";
import { createSimpleContext } from "./common";
import { useTuiConfig } from "../../config/tui";
import { VimEngine, type VimMode, type VimKeyEvent } from "../lib/vim-engine";

export const { use: useVim, provider: VimProvider } = createSimpleContext({
  name: "Vim",
  init: () => {
    const config = useTuiConfig();
    const enabled = config.vim ?? false;
    const engine = new VimEngine();
    const [mode, setMode] = createSignal<VimMode>(
      enabled ? "normal" : "insert",
    );

    return {
      get enabled() {
        return enabled;
      },
      get mode() {
        return mode();
      },
      handleKey(event: VimKeyEvent, text: string, cursor: number) {
        const result = engine.handleKey(event, text, cursor);
        if (result.modeChange) {
          setMode(result.modeChange);
        }
        return result;
      },
      reset() {
        engine.reset();
        setMode(enabled ? "normal" : "insert");
      },
    };
  },
});
```

the provider's job is to bridge the pure engine to SolidJS reactivity. `mode` is a signal so any component that reads `vim.mode` will re-render when the mode changes. the engine itself doesn't know about signals -- it returns `modeChange` in the result, and the provider calls `setMode` when it sees one.

`VimProvider` gets added to the provider tree in `app.tsx`, nested inside `TuiConfigProvider` (since it reads the config) but outside `Prompt` (since the prompt consumes it).

### layer 4: prompt integration

`packages/opencode/src/cli/cmd/tui/component/prompt/index.tsx` has three touch points.

**1. hook call** -- alongside the other context hooks at the top of the component:

```typescript
const vim = useVim();
```

**2. key interception** -- at the top of the `onKeyDown` handler, right after the disabled check:

```typescript
if (vim.enabled) {
  const result = vim.handleKey(
    { key: e.name, ctrl: !!e.ctrl, shift: !!e.shift, meta: !!e.meta },
    input.plainText,
    input.cursorOffset,
  );
  if (result.consumed) {
    e.preventDefault();
    if (result.newText !== undefined) {
      input.setText(result.newText);
      syncExtmarksWithPromptParts();
      setStore("prompt", "input", result.newText);
    }
    if (result.newCursor !== undefined) {
      input.cursorOffset = result.newCursor;
    }
    return;
  }
}
```

when `consumed` is true, we apply the result and return early. the key never reaches the textarea's default handler. when `consumed` is false (insert mode, regular typing), we fall through and the textarea handles it normally.

`syncExtmarksWithPromptParts()` is an existing function in the prompt component that re-applies syntax highlighting after text changes. we call it whenever we modify text through the vim engine, same as any other text modification path.

`setStore("prompt", "input", result.newText)` keeps the SolidJS store in sync with the textarea content. the store is the source of truth for the prompt value that gets sent to the agent.

**3. mode indicator** -- in the tray section of the prompt JSX:

```tsx
<Show when={vim.enabled}>
  <text fg={theme.textMuted}>
    {vim.mode === "normal" ? "-- NORMAL --" : "-- INSERT --"}
  </text>
</Show>
```

this only renders when vim is enabled. the `vim.mode` signal drives it reactively -- when you press `i` to enter insert mode, the indicator updates immediately.

## cross-referencing against neovim's source

the spec from claude code's docs tells you what commands exist. it doesn't tell you the exact semantics. for that, we went to neovim's C source.

the key files:

- `src/nvim/textobject.c` -- word motions (`fwd_word`, `bck_word`, `end_word`) and the `cls()` character classification function
- `src/nvim/normal.c` -- normal mode dispatch table, including the `cw` special case
- `src/nvim/charset.c` / `src/nvim/mbyte.c` -- character classification (`utf_class`)

### character classification

word motions in vim depend on character classification. from `textobject.c` around line 271:

```c
static int cls(void) {
  int c = gchar_cursor();
  if (c == ' ' || c == '\t' || c == NUL) return 0;
  c = utf_class(c);
  if (c != 0 && cls_bigword) return 1;  // W/B/E: all non-blank = class 1
  return c;
}
```

three classes: 0 = whitespace, 1 = punctuation, 2+ = keyword characters. `cls_bigword` is set when processing `W/B/E` motions (WORD, not word), which treat all non-whitespace as the same class.

the default `iskeyword` setting is `@,48-57,_,192-255`, which expands to `[a-zA-Z0-9_]` plus the Latin-1 supplement range (characters 192-255). our `isWordChar` function uses `/[A-Za-z0-9_]/`, which matches the ASCII portion. for a prompt input that's mostly code and English text, this is correct.

the `w` motion algorithm from `fwd_word` in `textobject.c`:

1. get the class of the character at cursor
2. skip all characters of the same class
3. skip whitespace
4. you're now at the start of the next word

in C, the inner loop looks roughly like:

```c
// simplified from fwd_word()
int cls_start = cls();
while (!end_of_buffer()) {
  inc_cursor();
  if (cls() != cls_start) break;
}
// now skip whitespace
while (!end_of_buffer() && cls() == 0) {
  inc_cursor();
}
```

our TypeScript equivalent:

```typescript
function findNextWordStart(text: string, cursor: number): number {
  if (cursor >= text.length - 1) return cursor;
  const startClass = charClass(text[cursor]);
  let i = cursor;
  // skip same class
  while (i < text.length - 1 && charClass(text[i + 1]) === startClass) {
    i++;
  }
  i++;
  // skip whitespace
  while (i < text.length && (text[i] === " " || text[i] === "\t")) {
    i++;
  }
  return i;
}

function charClass(ch: string): number {
  if (ch === " " || ch === "\t" || ch === "") return 0;
  if (isWordChar(ch)) return 2;
  return 1; // punctuation
}
```

the `b` motion is the reverse: skip whitespace backward, then skip same-class characters backward. in TypeScript:

```typescript
function findPrevWordStart(text: string, cursor: number): number {
  if (cursor <= 0) return 0;
  let i = cursor - 1;
  // skip whitespace
  while (i > 0 && (text[i] === " " || text[i] === "\t")) {
    i--;
  }
  // skip same class backward
  const endClass = charClass(text[i]);
  while (i > 0 && charClass(text[i - 1]) === endClass) {
    i--;
  }
  return i;
}
```

the symmetry between `w` and `b` is clean. `w` skips forward past same-class then whitespace. `b` skips backward past whitespace then same-class. the only asymmetry is that `w` ends at the _start_ of the next word while `b` ends at the _start_ of the previous word -- both are word-start positions, just in different directions.

### three bugs found

**bug 1: `cw` should behave like `ce`**

from `normal.c` around line 5951:

```c
/*
 * "cw" is a special case - it works like "ce" if the cursor is
 * on a non-blank.  This is not Vi compatible, but it's what Vim
 * has always done.
 */
if (cap->cmdchar == 'c' && cap->nchar == 'w'
    && !u_save_cursor()
    && !lineempty(curwin->w_cursor.lnum)) {
  if (!vim_iswhite(gchar_cursor())) {
    cap->nchar = 'e';
  }
}
```

the comment says it all. `cw` maps to `ce` when the cursor is on a non-blank character. this is not Vi compatible -- it's a Vim-specific behavior that's been there long enough that everyone expects it.

our initial implementation treated `cw` as a normal `c` + `w` composition, which deleted from cursor to the start of the next word (including the whitespace between words). the fix: in `applyOperator`, when the operator is `c` and the motion is `w`, check if the cursor is on whitespace. if not, redirect the motion to `e`.

```typescript
// in applyOperator
if (op === "c" && motion === "w") {
  const ch = text[cursor] ?? "";
  if (ch !== " " && ch !== "\t" && ch !== "") {
    motion = "e";
  }
}
```

**bug 2: `e` motion starting position**

neovim's `end_word` function always calls `inc_cursor()` first -- it advances at least one character before looking for the end of a word. this means pressing `e` when you're already at the end of a word moves to the end of the _next_ word.

our initial `findNextWordEnd` started at `cursor`:

```typescript
// wrong
let i = cursor;
while (i < text.length - 1 && isWordChar(text[i + 1])) {
  i++;
}
```

if the cursor is at the last character of a word, this loop doesn't advance at all and returns `cursor`. pressing `e` does nothing.

the fix is `let i = cursor + 1`:

```typescript
// correct
let i = cursor + 1;
if (i >= text.length) return cursor;
// skip whitespace
while (i < text.length && (text[i] === " " || text[i] === "\t")) {
  i++;
}
// find end of word
while (i < text.length - 1 && isWordChar(text[i]) && isWordChar(text[i + 1])) {
  i++;
}
return i;
```

**bug 3: `iw` on whitespace**

vim's documentation for `iw` (inner word): "Select [count] words (see |word|). White space between words is counted too, see |aw| if you don't want this."

the actual behavior when the cursor is on whitespace: `iw` selects the whitespace run itself, not the adjacent word. `aw` selects the whitespace plus the adjacent word.

our initial implementation jumped to the adjacent word when the cursor was on whitespace, which is wrong. the fix:

```typescript
function findWordRange(
  text: string,
  cursor: number,
  inner: boolean,
): [number, number] {
  const onWhitespace = text[cursor] === " " || text[cursor] === "\t";

  if (onWhitespace) {
    // find the whitespace run
    let start = cursor;
    let end = cursor;
    while (start > 0 && (text[start - 1] === " " || text[start - 1] === "\t"))
      start--;
    while (
      end < text.length - 1 &&
      (text[end + 1] === " " || text[end + 1] === "\t")
    )
      end++;

    if (!inner) {
      // aw: include the adjacent word (prefer the word after the whitespace)
      if (end + 1 < text.length && isWordChar(text[end + 1])) {
        while (end + 1 < text.length && isWordChar(text[end + 1])) end++;
      } else if (start > 0 && isWordChar(text[start - 1])) {
        while (start > 0 && isWordChar(text[start - 1])) start--;
      }
    }
    return [start, end];
  }

  // cursor is on a word character
  let start = cursor;
  let end = cursor;
  while (start > 0 && isWordChar(text[start - 1])) start--;
  while (end < text.length - 1 && isWordChar(text[end + 1])) end++;

  if (!inner) {
    // aw: include trailing whitespace (or leading if at end of line)
    if (
      end + 1 < text.length &&
      (text[end + 1] === " " || text[end + 1] === "\t")
    ) {
      while (
        end + 1 < text.length &&
        (text[end + 1] === " " || text[end + 1] === "\t")
      )
        end++;
    } else if (
      start > 0 &&
      (text[start - 1] === " " || text[start - 1] === "\t")
    ) {
      while (start > 0 && (text[start - 1] === " " || text[start - 1] === "\t"))
        start--;
    }
  }
  return [start, end];
}
```

**the escape key name bug**

this one wasn't from neovim source -- it came up during live testing. `@opentui/core` sends the escape key as `"escape"` (lowercase). we were checking for `"Escape"` (capital E). the engine never saw escape key events, so you couldn't exit insert mode.

the fix is a single character change in the key dispatch:

```typescript
if (event.key === "escape") {
  // not "Escape"
  return this.enterNormal(text, cursor);
}
```

worth noting because it's the kind of thing that's invisible in unit tests if you're not careful about what key names your test framework uses.

## full vim mode reference

### mode switching

| key   | action                                        |
| ----- | --------------------------------------------- |
| `i`   | enter insert mode at cursor                   |
| `I`   | enter insert mode at first non-blank of line  |
| `a`   | enter insert mode after cursor                |
| `A`   | enter insert mode at end of line              |
| `o`   | open new line below, enter insert mode        |
| `O`   | open new line above, enter insert mode        |
| `Esc` | return to normal mode / clear pending command |

### navigation (normal mode)

| key       | action                                                |
| --------- | ----------------------------------------------------- |
| `h`       | move left                                             |
| `j`       | move down (next line)                                 |
| `k`       | move up (previous line)                               |
| `l`       | move right                                            |
| `w`       | next word start                                       |
| `e`       | end of current/next word                              |
| `b`       | previous word start                                   |
| `W`       | next WORD start (whitespace-delimited)                |
| `E`       | end of current/next WORD                              |
| `B`       | previous WORD start                                   |
| `0`       | beginning of line                                     |
| `$`       | end of line                                           |
| `^`       | first non-blank character of line                     |
| `gg`      | beginning of buffer                                   |
| `G`       | end of buffer                                         |
| `f{char}` | jump to next occurrence of {char} on current line     |
| `F{char}` | jump to previous occurrence of {char} on current line |
| `t{char}` | jump to just before next {char} on current line       |
| `T{char}` | jump to just after previous {char} on current line    |
| `;`       | repeat last f/F/t/T in same direction                 |
| `,`       | repeat last f/F/t/T in opposite direction             |

### editing (normal mode)

| key         | action                                                              |
| ----------- | ------------------------------------------------------------------- |
| `x`         | delete character at cursor                                          |
| `dd`        | delete entire line                                                  |
| `D`         | delete from cursor to end of line                                   |
| `dw`        | delete to next word start                                           |
| `de`        | delete to end of word                                               |
| `db`        | delete to previous word start                                       |
| `d0`        | delete to beginning of line                                         |
| `d$`        | delete to end of line                                               |
| `d{motion}` | delete with any supported motion                                    |
| `cc`        | change entire line (delete + enter insert)                          |
| `C`         | change from cursor to end of line                                   |
| `cw`        | change to end of word (behaves like `ce`)                           |
| `ce`        | change to end of word                                               |
| `cb`        | change to previous word start                                       |
| `c{motion}` | change with any supported motion                                    |
| `yy` / `Y`  | yank entire line into register                                      |
| `yw`        | yank to next word start                                             |
| `ye`        | yank to end of word                                                 |
| `yb`        | yank to previous word start                                         |
| `y{motion}` | yank with any supported motion                                      |
| `p`         | paste register after cursor (linewise: below current line)          |
| `P`         | paste register before cursor (linewise: above current line)         |
| `>>`        | indent current line by one shiftwidth                               |
| `<<`        | dedent current line by one shiftwidth                               |
| `J`         | join current line with next (adds space, strips leading whitespace) |
| `.`         | repeat last change                                                  |

### text objects (used with d/c/y in normal mode)

| text object | description                                                             |
| ----------- | ----------------------------------------------------------------------- |
| `iw`        | inner word -- the word under cursor, or whitespace run if on whitespace |
| `aw`        | around word -- word plus surrounding whitespace                         |
| `iW`        | inner WORD -- whitespace-delimited token                                |
| `aW`        | around WORD -- WORD plus surrounding whitespace                         |
| `i"`        | inner double quotes -- content between `"..."`                          |
| `a"`        | around double quotes -- includes the quote characters                   |
| `i'`        | inner single quotes -- content between `'...'`                          |
| `a'`        | around single quotes -- includes the quote characters                   |
| `i(`        | inner parentheses -- content between `(...)`                            |
| `a(`        | around parentheses -- includes the parentheses                          |
| `i[`        | inner square brackets -- content between `[...]`                        |
| `a[`        | around square brackets -- includes the brackets                         |
| `i{`        | inner curly braces -- content between `{...}`                           |
| `a{`        | around curly braces -- includes the braces                              |

### not supported (matching claude code)

| feature                      | reason                           |
| ---------------------------- | -------------------------------- |
| visual mode (`v/V`)          | not in claude code's feature set |
| count prefixes (`3j`, `5dd`) | not in claude code's feature set |
| undo/redo (`u`, `Ctrl+R`)    | not in claude code's feature set |
| search (`/`, `?`, `n`, `N`)  | not in claude code's feature set |
| replace char (`r`)           | not in claude code's feature set |
| marks (`m`, `` ` ``, `'`)    | not in claude code's feature set |
| registers (`"a`, `"b`, etc.) | not in claude code's feature set |
| ex commands (`:`)            | not in claude code's feature set |
| macros (`q`, `@`)            | not in claude code's feature set |

## how to try it

the full source is on github: [sngeth/opencode (feat/vim-keybindings)](https://github.com/sngeth/opencode/tree/feat/vim-keybindings)

```bash
git clone https://github.com/sngeth/opencode.git
cd opencode
git checkout feat/vim-keybindings
bun install
```

create `~/.config/opencode/tui.json` to enable vim mode globally:

```json
{
  "vim": true
}
```

you can also use `.opencode/tui.json` in a specific project directory, but the global path is better when running the compiled binary since CWD changes per project.

### running as a compiled binary (recommended)

`bun run dev` from `packages/opencode/` works but locks your terminal to the repo directory. sessions and file paths resolve relative to `process.cwd()`, so you want to invoke it from the project you're actually working on.

compile a native binary instead. bun bundles everything -- dependencies, the SolidJS JSX transform, tree-sitter parsers, migrations -- into a single executable:

```bash
# from packages/opencode
bun run build --single --skip-install
```

this produces a ~116MB binary at `dist/opencode-<platform>-<arch>/bin/opencode`. symlink it somewhere on your `$PATH` under a name that won't shadow the official opencode binary:

```bash
ln -sf $(pwd)/dist/opencode-darwin-arm64/bin/opencode ~/.local/bin/opencode-vim
```

now `opencode-vim` works from any directory. sessions are scoped correctly and the official `opencode` stays untouched. rebuild after source changes with `--single --skip-install` (~10 seconds).

the mode indicator appears in the prompt tray. it shows `-- NORMAL --` when you're in normal mode and `-- INSERT --` when you're in insert mode. opencode starts in normal mode when vim is enabled, same as neovim's default.

if you want to start in insert mode automatically, press `i` after the prompt loads. there's no config option for the initial mode -- that's a deliberate choice to match how vim itself works.

## files changed

| file                                                           | change                                                   |
| -------------------------------------------------------------- | -------------------------------------------------------- |
| `packages/opencode/src/config/tui-schema.ts`                   | added `vim: z.boolean().optional()` field                |
| `packages/opencode/src/cli/cmd/tui/lib/vim-engine.ts`          | NEW -- 957-line pure TypeScript state machine            |
| `packages/opencode/src/cli/cmd/tui/context/vim.tsx`            | NEW -- 35-line SolidJS context wrapping the engine       |
| `packages/opencode/src/cli/cmd/tui/app.tsx`                    | added `VimProvider` to the provider tree                 |
| `packages/opencode/src/cli/cmd/tui/component/prompt/index.tsx` | key interception in `onKeyDown` + mode indicator in tray |

five files. the engine is the bulk of it. the integration is thin by design -- the engine does the work, the prompt just routes keys through it and applies the results.

the pure engine approach paid off during debugging. when the `cw` behavior was wrong, we could write a test that called `engine.handleKey` directly with a string and cursor position, without spinning up a terminal or a SolidJS component tree. the neovim source comparison was also easier because we were comparing TypeScript logic to C logic, not trying to trace through UI event handling at the same time.

the `escape` key name bug is a good reminder that integration tests matter even when unit tests pass. the engine was correct. the key name mismatch was in the boundary between `@opentui/core`'s event format and our engine's expected format. that boundary only exists in the running application.

## more gotchas (found after shipping)

the initial post covered three bugs found during development. three more showed up after the implementation was running in daily use.

### `x` silently fails on trailing spaces

the symptom: pressing `x` at the end of a line with a trailing space does nothing. the character is there, the cursor is on it, but `x` returns without deleting.

the root cause is a cursor model mismatch. `@opentui/core`'s `TextareaRenderable.cursorOffset` is a gap-position -- it sits between characters, like a text insertion point. vim's normal mode cursor is a cell-position -- it sits on a character. for the string `"xxx "` (four characters), `cursorOffset=4` means "after the space" in the gap model. in vim's model, that position doesn't exist: the valid range is 0-3.

the `x` handler had an early return for this case:

```typescript
if (safeCursor >= text.length) return { consumed: true };
```

when `cursorOffset=4` and `text.length=4`, this fires and returns without deleting anything. the user sees nothing happen.

the same mismatch caused a second problem: pressing `Escape` to exit insert mode didn't move the cursor left by one position. real neovim does this -- if you're at the end of a word in insert mode and press `Escape`, the cursor steps back one character so it's sitting on the last character rather than past it. without that adjustment, the cursor stays at offset 4 after switching to normal mode, which puts it in the gap-position zone where operations silently fail.

two fixes in `vim-engine.ts`:

```typescript
// before -- safeCursor could equal text.length in normal mode
const safeCursor = this.clamp(cursor, 0, text.length);

// after -- clamp to text.length - 1 so cursor is always on a character
const safeCursor = text.length > 0 ? this.clamp(cursor, 0, text.length - 1) : 0;
```

```typescript
// before -- escape exits insert mode but leaves cursor at end-of-text gap position
return { consumed: true, modeChange: "normal" };

// after -- step cursor back one, matching neovim's behavior
return {
  consumed: true,
  newCursor: text.length > 0 ? Math.max(0, cursor - 1) : 0,
  modeChange: "normal",
};
```

the clamping fix is the more important one. any operation that checked `safeCursor >= text.length` or `safeCursor >= end` would silently fail when the cursor was at the end of text. `x` was the most visible case, but the same condition could affect other operators.

### every shifted command is silently broken

pressing `Shift+j` to join lines moved the cursor down instead. pressing `Shift+o` to open a line above did nothing visible. every uppercase command -- `J`, `O`, `A`, `I`, `G`, `D`, `C`, `Y`, `P`, `W`, `E`, `B`, `F`, `T` -- was broken.

`@opentui/core` sends key events with the base character in `e.name` (always lowercase) and shift state as a separate boolean `e.shift`. so `Shift+j` arrives as `{ name: "j", shift: true }`, not `{ name: "J" }`. the vim engine was doing `const key = event.key` and checking against uppercase literals like `if (key === "J")`. the key was always lowercase. the uppercase branch never matched.

the lowercase branch matched instead: `if (key === "j")` → move down. `Shift+j` moved the cursor down when it should have joined lines. `Shift+o` hit `if (key === "o")` → open line below instead of above.

the fix is one line at the top of `handleKey`:

```typescript
// before
const key = event.key;

// after
const key =
  event.shift && event.key.length === 1 ? event.key.toUpperCase() : event.key;
```

when shift is held and the key is a single character, uppercase it before dispatch. this is the kind of bug that's invisible in unit tests where you construct key events with the character you expect (`"J"`) rather than the character the framework actually sends (`"j"` + `shift: true`).

## escape key routing during generation

opencode has a session interrupt command -- when a task is running, pressing `Escape` should abort the generation. after adding vim mode, that stopped working. pressing `Escape` during generation always triggered the interrupt instead of letting vim switch from insert to normal mode.

the root cause wasn't in the textarea's `onKeyDown` handler at all. opencode's command system registers a global `useKeyboard` handler in `dialog-command.tsx` that fires **before** any component-level key handler:

```typescript
// dialog-command.tsx -- global handler, fires first
useKeyboard((evt) => {
  if (suspended()) return;
  if (dialog.stack.length > 0) return;
  for (const option of entries()) {
    if (!isEnabled(option)) continue;
    if (option.keybind && keybind.match(option.keybind, evt)) {
      evt.preventDefault();
      option.onSelect?.(dialog);
      return;
    }
  }
});
```

the `session_interrupt` command is registered with `keybind: "session_interrupt"` (mapped to `"escape"`) and `enabled: status().type !== "idle"`. during generation, every `Escape` keypress matches the interrupt command before the textarea ever sees it. vim never gets a chance to handle the key.

the fix is one line -- make the interrupt command aware of vim's mode:

```typescript
// before
enabled: status().type !== "idle",

// after
enabled: status().type !== "idle" && !(vim.enabled && vim.mode === "insert"),
```

when vim is in insert mode, the interrupt command is disabled. `Escape` passes through the global handler without matching, reaches the textarea's `onKeyDown`, and vim processes it normally (insert to normal). on the next `Escape`, vim is in normal mode, the interrupt command is enabled again, and the abort fires.

the resulting behavior:

| mode   | task running | `Escape` does             |
| ------ | ------------ | ------------------------- |
| insert | yes          | switches to normal mode   |
| normal | yes          | interrupts the generation |
| insert | no           | switches to normal mode   |
| normal | no           | clears pending command    |

this gives you the two-step sequence that feels natural: `Escape` to get to normal mode, `Escape` again to interrupt. it matches the mental model of "escape gets me out of whatever I'm in" -- first out of insert mode, then out of the generation.
