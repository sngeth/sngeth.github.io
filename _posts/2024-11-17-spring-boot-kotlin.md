---
layout: post
title: "Modernizing the Spring Boot Kotlin Tutorial: A Developer's Guide with Neovim"
category: "Kotlin"
comments: true
---

After over a 6-year hiatus from Spring Boot in my professional work, I found myself curious about how the ecosystem had evolved.
I wondered if I could make it work without reaching for the traditional IntelliJ IDEA approach, because "nvim btw".
Here's what I discovered while attempting to modernize a Spring Boot Kotlin tutorial using just Neovim as my development environment.
Neovim boots up in less than a second and compilation is blazing fast.

## The State of the Tutorial

The original [Spring Boot Kotlin tutorial](https://spring.io/guides/tutorials/spring-boot-kotlin), despite its age, remains surprisingly relevant. However, there are several key modern considerations:

- Gradle configuration now uses the Kotlin DSL (`build.gradle.kts`)
- Updated dependencies including Spring Boot 3.x and Kotlin 1.9.x
- Modern Java toolchain requirements (JDK 21)
- Usage of Jakarta EE instead of javax packages
- Enhanced Kotlin compiler options and Spring plugin configurations

## Project Setup

Before diving into development, you'll need to set up your environment. Here's what you need:

### Prerequisites

1. **Java Development Kit (JDK) 21**
   ```bash
   brew install openjdk@21
   ```
   After installation, make sure JAVA_HOME is set correctly in your shell configuration.

2. **Gradle Build Tool**
   ```bash
   brew install gradle
   ```
   While the project includes the Gradle wrapper (`gradlew`), having Gradle installed locally can be helpful for other Kotlin projects.

3. **Clone and Build**
   ```bash
   git clone https://github.com/sngeth/spring-boot-kotlin-demo
   cd spring-boot-kotlin-demo
   ./gradlew build
   ```

## Neovim as Your Kotlin IDE

One of the most interesting aspects of this journey was using Neovim instead of traditional IDEs like IntelliJ IDEA. Here's how to make Neovim a powerful Kotlin development environment:

### Essential Tools

1. **Kotlin Language Server**: The backbone of Kotlin development in Neovim
   - Provides code completion
   - Offers type information
   - Handles syntax highlighting
   - Detects missing imports automatically

   ```bash
   brew install kotlin-language-server
   ```

2. **LSP Configuration**:
   ```lua
   require('lspconfig').kotlin_language_server.setup({
     cmd = { "kotlin-language-server" },
     filetypes = { "kotlin" },
     root_dir = require('lspconfig.util').root_pattern(
       "settings.gradle",
       "settings.gradle.kts",
       "build.gradle",
       "build.gradle.kts"
     )
   })
   ```

3. **Code Actions**: This functionality comes from multiple sources:
   - The built-in LSP client in Neovim (`:h lsp`)
   - `nvim-cmp` for completion
   - `null-ls` or `none-ls` for additional formatting
   - Popular plugins like `nvim-code-action-menu`

### Development Workflow

Instead of relying on IDE-integrated build tools, the workflow becomes:

```bash
./gradlew build -t
```

This continuous build approach:
- Watches for file changes
- Recompiles automatically
- Provides quick feedback on errors
- Eliminates the need for IDE-specific build processes

### Advantages of This Setup

1. **Lightweight Development Environment**
   - Faster startup times
   - Lower resource usage
   - Familiar Vim keybindings

2. **Modern Development Features**
   - Code completion via LSP
   - Inline error highlighting
   - Jump-to-definition functionality
   - Symbol search across the project

3. **Build Process Transparency**
   - Clear visibility of the build process
   - Direct control over Gradle commands
   - No IDE abstraction layer

## Common Pitfalls and Solutions

1. **Import Management**
   - Challenge: Missing IDE auto-import
   - Solution: Kotlin Language Server handles this effectively
   - Tip: Use `:LspRestart` if imports aren't updating

2. **Compile Error Detection**
   - Challenge: No immediate visual feedback
   - Solution: Continuous Gradle build (`-t` flag)
   - Enhancement: Configure quickfix list integration

3. **Code Actions Availability**
   - Challenge: Understanding source of actions
   - Solution: Multiple plugins working together:
     - LSP for basic actions
     - Additional plugins for enhanced functionality
     - Custom keybindings for frequent actions


![Spring Boot with Kotlin Development](/public/images/kotlin-lsp.png){: .img-fluid .mx-auto .d-block style="max-width: 100%; height: auto;"}


## Recommended Neovim Plugins for Kotlin Development

1. Base LSP Setup:
   ```lua
   'neovim/nvim-lspconfig'
   'hrsh7th/nvim-cmp'
   'hrsh7th/cmp-nvim-lsp'
   ```

2. Enhanced Functionality:
   ```lua
   'nvim-code-action-menu'
   'telescope.nvim'
   'null-ls.nvim'
   ```

## Conclusion

While the Spring Boot Kotlin tutorial may be showing its age, the core concepts remain solid. Combining it with modern tools like Neovim and the Kotlin Language Server creates a powerful, efficient development environment. The continuous build approach with Gradle provides quick feedback, while LSP integration offers many features traditionally associated with full IDEs.

This setup proves that you don't need a heavy IDE to develop Spring Boot applications with Kotlin effectively. The combination of Neovim's efficiency, LSP's intelligence, and Gradle's build tools creates a streamlined, modern development experience that can rival traditional IDEs while maintaining the flexibility and lightness of a terminal-based workflow.
