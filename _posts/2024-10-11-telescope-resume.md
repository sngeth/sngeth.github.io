---
layout: post
title: Neovim Telescope
category: "Neovim"
comments: true
---
If you're a longtime Vim user like me, you've probably used the [CtrlP plugin](https://github.com/ctrlpvim/ctrlp.vim) at some point in your workflow. One of my favorite features in CtrlP was being able to hit `<C-p>` twice and instantly resume the last fuzzy search.
This simple trick saved me from having to repeat the same query again and again.

Recently, while transitioning to Neovim, I started using [Telescope](https://github.com/nvim-telescope/telescope.nvim), which offers a more powerful and extensible fuzzy finder.
But one feature I was really missing from CtrlP was the ability to **resume the last search** without retyping it.

## Resuming Your Last Search with Telescope

While this feature is mentioned in the Github Docs under the Vim Pickers section, there is no default keybinding for it, making it easy to overlook.

Telescope’s `resume` feature allows you to pull up your last search exactly where you left off. This is especially useful when you've closed the fuzzy finder, but want to bring it back with all the previous search context.

Here's how you can map the `resume` command to a shortcut key:

```lua
vim.keymap.set('n', '<leader>tr', '<cmd>Telescope resume<CR>', { noremap = true, silent = true })
```

Now, with `<leader>tr`, I can resume my last Telescope search instantly, just like I used to do with CtrlP by hitting `<C-p>` twice.


### Use Cases for `Telescope resume`

There are several moments when `resume` really shines:
- **Switching between buffers**: Maybe you started a fuzzy search for a file, got distracted by something else, and need to get back to it quickly.
- **Live grep continuation**: If you were performing a project-wide search using `live_grep` and closed the picker, you can immediately resume and continue refining your search.
- **Navigating between recently opened files**: If you were exploring multiple files and closed the search prematurely, `resume` will restore that exact file list.

## Sending Telescope Results to Quickfix List

Another powerful feature in Telescope that enhances your workflow is the ability to send your current search results to a quickfix list. This is particularly useful when you want to work with multiple results from your search.

By default, you can use `<C-q>` while in a Telescope picker to send all the current results to the quickfix list. This works for any Telescope picker, including file search, grep results, and more.

Here are some benefits of using this feature:

1. **Persistent Results**: The quickfix list persists even after you close the Telescope window, allowing you to refer back to your search results later.
2. **Batch Operations**: You can perform operations on multiple files in the quickfix list, such as search and replace across all results.
3. **Navigation**: Quickly jump between search results using quickfix navigation commands.

To use this feature:

1. Open any Telescope picker (e.g., `<leader>ff` for file search or `<leader>fg` for live grep)
2. Perform your search as usual
3. Press `<C-q>` to send the current results to the quickfix list
4. Close the Telescope window (optional)
5. Use `:copen` to open the quickfix window and navigate through your results
