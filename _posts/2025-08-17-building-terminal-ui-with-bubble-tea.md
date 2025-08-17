---
layout: post
title: "Building a Terminal IRC Client with Bubble Tea: A Deep Dive into Go's TUI Framework"
categories: [go, terminal, ui, bubble-tea]
---

When I decided to build a modern IRC client for the terminal, I wanted something more sophisticated than the typical ncurses-based applications. Enter [Bubble Tea](https://github.com/charmbracelet/bubbletea), Charm's powerful framework for building terminal user interfaces in Go. In this post, I'll walk through how Bubble Tea works and how I used it to create a feature-rich IRC client.

## What is Bubble Tea?

Bubble Tea is based on The Elm Architecture, bringing functional programming concepts to terminal UIs. It follows a simple pattern:

- **Model**: Your application state
- **Update**: A function that modifies state based on messages
- **View**: A function that renders the current state

This architecture makes applications predictable, testable, and easy to reason about.

## The Elm Architecture in Bubble Tea

According to the [Bubble Tea repository](https://github.com/charmbracelet/bubbletea), it's "based on the functional design paradigms of The Elm Architecture". Here's how it works:

### The Four Pillars

Every Bubble Tea program consists of:

1. **Model**: A struct that holds your entire application state
2. **Init()**: Returns the initial model and any startup commands
3. **Update(msg tea.Msg)**: Receives messages and returns an updated model
4. **View()**: Takes the model and returns a string representation

Here's the minimal interface every Bubble Tea program must implement:

```go
type Model interface {
    Init() Cmd
    Update(Msg) (Model, Cmd)
    View() string
}
```

### How It Works

A key concept: **You implement these methods, but you never call them**. The framework calls your code:

```go
// What you write:
func (m IRCModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.KeyMsg:
        // Handle user input
    case msgConnected:
        // Handle IRC connection
    }
    return m, nil
}

func main() {
    p := tea.NewProgram(InitialModel())
    p.Run()  // You call this once, then Bubble Tea takes over
}
```

**Inside `p.Run()`**, Bubble Tea's event loop calls your methods:

```go
// What Bubble Tea does (you never write this):
for {
    select {
    case msg := <-p.msgs:
        model, cmd = model.Update(msg)  // Framework calls YOUR Update
        handleCommand(cmd)              // Framework handles returned command
        render(model.View())            // Framework calls YOUR View
    }
}
```

### The Message Flow

The genius of this architecture is its unidirectional data flow:

```
    ┌─────────────────┐
    │                 │
    │     Model       │◄─────────────┐
    │                 │              │
    └────────┬────────┘              │
             │                       │
             ▼                       │
    ┌─────────────────┐              │
    │                 │              │
    │      View       │              │
    │                 │              │
    └────────┬────────┘              │
             │                       │
             ▼                       │
        Terminal                     │
         Display                     │
             │                       │
         User Input                  │
             │                       │
             ▼                       │
    ┌─────────────────┐              │
    │                 │              │
    │     Update      │──────────────┘
    │                 │
    └─────────────────┘
```

Messages flow in one direction: User input → Update → Model → View → Display. 

**Why this matters:** In traditional UI programming, different parts of your app can modify state directly, leading to chaos:

```go
// Traditional approach - multiple places changing state
func onKeyPress() {
    sidebar.addChannel("#golang")
    chatArea.updateUserCount(42)
    statusBar.setConnected(true)
    // Who changed what? When? In what order?
}

func onNetworkEvent() {
    sidebar.removeUser("bob")
    chatArea.addMessage("bob left")
    // Now sidebar and chat area might be out of sync!
}
```

With Bubble Tea's unidirectional flow, **only one place** can change state:

```go
// Bubble Tea approach - all changes go through Update
func (m IRCModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case UserLeftMsg:
        // Remove from users list
        delete(m.channelUsers[msg.channel], msg.user)
        // Add to message history  
        m.addMessage(msg.channel, fmt.Sprintf("%s left", msg.user))
        // State is always consistent!
    }
    return m, nil
}
```

This guarantees your UI state is always consistent because there's only one path for changes.

### Why This Matters for Terminal UIs

Traditional terminal UI libraries like ncurses use imperative updates:

```c
// ncurses - imperative, stateful
mvprintw(10, 20, "Status: ");
if (connected) {
    attron(COLOR_PAIR(GREEN));
    printw("Connected");
} else {
    attron(COLOR_PAIR(RED));
    printw("Disconnected");
}
refresh();
```

With Bubble Tea's Elm Architecture:

```go
// Bubble Tea - declarative, functional
func (m Model) View() string {
    status := "Disconnected"
    if m.connected {
        status = "Connected"
    }
    return fmt.Sprintf("Status: %s", status)
}
```

The framework handles all the diffing, rendering, and optimization. You just describe what you want to see.

## The Core Architecture

Here's how I structured the IRC client using Bubble Tea:

```go
type IRCModel struct {
    // UI components
    viewport        viewport.Model
    sidebarViewport viewport.Model
    textarea        textarea.Model
    
    // Application state
    allMessages     map[string][]string
    channels        map[string]bool
    channelUsers    map[string][]string
    activeChannel   string
    sidebarFocused  bool
    connected       bool
    
    // Layout
    width           int
    height          int
    sidebarWidth    int
}
```

The model contains both UI components (viewports, textarea) and application state (channels, messages, users). This separation allows for clean state management while leveraging Bubble Tea's built-in components.

## The Update Loop

The heart of any Bubble Tea application is the `Update` function, which handles all events:

```go
func (m IRCModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    // Route input based on focus
    if !m.sidebarFocused {
        m.textarea, tiCmd = m.textarea.Update(msg)
        m.viewport, vpCmd = m.viewport.Update(msg)
    } else {
        m.sidebarViewport, svpCmd = m.sidebarViewport.Update(msg)
    }

    switch msg := msg.(type) {
    case tea.WindowSizeMsg:
        m.handleResize(msg)
        
    case tea.KeyMsg:
        return m.handleKeypress(msg)
        
    case msgConnected:
        return m.handleConnection(msg)
        
    case msgReceived:
        return m.handleIRCMessage(msg)
    }
    
    return m, tea.Batch(tiCmd, vpCmd, svpCmd)
}
```

Notice how different message types are handled separately. This pattern makes it easy to add new features without breaking existing functionality.

## Custom Message Types

One powerful feature of Bubble Tea is custom message types. For IRC, I created specific messages for different network events:

```go
type msgConnected struct {
    conn net.Conn
}

type msgReceived struct {
    text string
}

type errMsg error
```

These messages are sent through commands, which are functions that return messages:

```go
func connectToIRC(server, nickname string) tea.Cmd {
    return func() tea.Msg {
        conn, err := net.Dial("tcp", server)
        if err != nil {
            return errMsg(err)
        }
        
        // Send IRC registration
        writer := bufio.NewWriter(conn)
        writer.WriteString(fmt.Sprintf("NICK %s\r\n", nickname))
        writer.WriteString(fmt.Sprintf("USER %s 0 * :%s\r\n", nickname, nickname))
        writer.Flush()
        
        return msgConnected{conn: conn}
    }
}
```

This approach keeps the UI responsive while handling network operations in the background.

## Layout with Golden Ratio

For the visual design, I implemented a golden ratio layout to create pleasing proportions:

```go
goldenRatio := 1.618
m.sidebarWidth = int(float64(msg.Width) / (goldenRatio + 1.0))

// Ensure reasonable bounds
if m.sidebarWidth < 15 {
    m.sidebarWidth = 15
}
if m.sidebarWidth > 25 {
    m.sidebarWidth = 25
}
```

This creates a sidebar that's approximately 38% of the screen width, following the golden ratio principle for visual harmony.

## Independent Scrolling with Focus Management

One challenge was implementing independent scrolling for the sidebar and main chat area. I solved this with a focus system:

```go
case tea.KeyTab:
    m.sidebarFocused = !m.sidebarFocused
    if m.sidebarFocused {
        m.textarea.Blur()
    } else {
        m.textarea.Focus()
    }
```

When the sidebar is focused, arrow keys scroll through channels and users. When the chat is focused, they scroll through message history. This gives users full control over both areas independently.

## Real-time Updates

IRC requires real-time message handling. I set up a continuous message loop:

```go
func waitForMessage(conn net.Conn) tea.Cmd {
    return func() tea.Msg {
        scanner := bufio.NewScanner(conn)
        if scanner.Scan() {
            return msgReceived{text: scanner.Text()}
        }
        if err := scanner.Err(); err != nil {
            return errMsg(err)
        }
        return nil
    }
}
```

Each time a message is received, it triggers an update, parses the IRC protocol, and updates the appropriate channel or user list.

## Styling with Lipgloss

Bubble Tea integrates beautifully with [Lipgloss](https://github.com/charmbracelet/lipgloss) for styling. I created adaptive styles that work in both light and dark terminals:

```go
var (
    titleStyle = lipgloss.NewStyle().
        Foreground(lipgloss.AdaptiveColor{Light: "#FFFFFF", Dark: "#FFFDF5"}).
        Background(lipgloss.AdaptiveColor{Light: "#0969DA", Dark: "#25A065"}).
        Padding(0, 1)

    userStyle = lipgloss.NewStyle().
        Foreground(lipgloss.AdaptiveColor{Light: "#1A7F37", Dark: "#7EE787"})
)
```

This ensures the client looks great regardless of the terminal's color scheme.

## Under the Hood: How Bubble Tea Prevents UI Blocking

Looking at the Bubble Tea source code reveals elegant concurrency patterns that keep the UI responsive. Here's how it actually works:

### The Message Channel Architecture

Bubble Tea uses a central message channel (`p.msgs`) as the communication hub:

```go
func (p *Program) Send(msg Msg) {
    select {
    case <-p.ctx.Done():
    case p.msgs <- msg:
    }
}
```

This channel allows background goroutines to safely send messages back to the main event loop without blocking.

### Command Execution in Goroutines

When you return a `tea.Cmd`, Bubble Tea spawns a goroutine to execute it:

```go
func (p *Program) handleCommands(cmds chan Cmd) chan struct{} {
    go func() {
        for {
            select {
            case cmd := <-cmds:
                go func() {
                    // Each command runs in its own goroutine
                    msg := cmd()
                    p.Send(msg)  // Send result back to main loop
                }()
            }
        }
    }()
}
```

**Key benefits:**
1. **Non-blocking execution** - Long-running operations don't freeze the UI
2. **Automatic panic recovery** - Crashed commands don't take down the app
3. **Graceful cleanup** - Context cancellation stops all goroutines on exit

### The Event Loop

The main event loop processes messages sequentially, ensuring thread safety:

```go
func (p *Program) eventLoop(model Model, cmds chan Cmd) (Model, error) {
    for {
        select {
        case msg := <-p.msgs:
            // Update model (always on main thread)
            model, cmd = model.Update(msg)
            
            // Send new commands for background execution
            select {
            case cmds <- cmd:
            case <-p.ctx.Done():
                return model, nil
            }
            
            // Render immediately with updated model
            p.renderer.write(model.View())
        }
    }
}
```

### Why This Design Matters

In your IRC client, when `connectToIRC()` makes a network call:

1. **Network operation runs in background goroutine** (doesn't block UI)
2. **User can still type, scroll, resize** (UI remains responsive)  
3. **When connection completes, sends `msgConnected`** (thread-safe communication)
4. **Main loop processes message and updates model** (sequential, no race conditions)
5. **UI re-renders with new state** (immediate visual feedback)

This is why you can have dozens of ongoing network operations (IRC reads, user lookups, etc.) without any UI lag or complex synchronization code.

## Source Code

You can check out the complete IRC client source code at [github.com/sngeth/chat](https://github.com/sngeth/chat).