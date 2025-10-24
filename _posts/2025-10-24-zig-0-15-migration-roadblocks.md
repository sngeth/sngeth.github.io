---
layout: post
title: "migrating to zig 0.15: the roadblocks nobody warned you about"
date: 2025-10-24
categories: zig systems-programming breaking-changes
---

i built a command-line security tool to analyze shell scripts before executing them (preventing those dangerous `curl | bash` situations). starting with zig 0.15 meant hitting every breaking change head-on. here's what actually broke and how to fix it.

## the project: safe-curl

the tool analyzes shell scripts for malicious patterns:
- recursive file deletion (`rm -rf /`)
- code obfuscation (base64 decoding, eval)
- privilege escalation (sudo)
- remote code execution

zig seemed perfect for a simple CLI tool with minimal dependencies. then i hit the 0.15 changes.

source: [safe-curl on github](https://github.com/sngeth/safe-curl-zig)

## roadblock 1: arraylist requires allocator everywhere

**the change**: zig 0.15 replaced `std.ArrayList` with `std.array_list.Managed` as the default. the "managed" variant now requires passing an allocator to every method call.

**official reasoning**: [zig 0.15 release notes](https://ziglang.org/download/0.15.1/release-notes.html) explain: "Having an extra field is more complicated than not having an extra field." the unmanaged variant is now the primary implementation, with the managed version as a wrapper.

### what broke

my initial attempt looked like this:

```zig
const Finding = struct {
    severity: Severity,
    message: []const u8,
    line_num: usize,
};

const AnalysisResult = struct {
    findings: std.ArrayList(Finding),

    fn init(allocator: std.mem.Allocator) AnalysisResult {
        return .{
            .findings = std.ArrayList(Finding).init(allocator),
        };
    }

    fn addFinding(self: *AnalysisResult, finding: Finding) !void {
        try self.findings.append(finding);  // Error: missing allocator
    }
};
```

**error message**:
```
error: expected 2 arguments, found 1
```

### the fix

you have two options in 0.15:

**option 1**: store the allocator and pass it to methods

```zig
const AnalysisResult = struct {
    findings: std.ArrayList(Finding),
    allocator: std.mem.Allocator,  // Store allocator

    fn init(allocator: std.mem.Allocator) AnalysisResult {
        return .{
            .findings = std.ArrayList(Finding).init(allocator),
            .allocator = allocator,
        };
    }

    fn addFinding(self: *AnalysisResult, finding: Finding) !void {
        try self.findings.append(self.allocator, finding);  // Pass allocator
    }

    fn deinit(self: *AnalysisResult) void {
        self.findings.deinit(self.allocator);  // Pass here too
    }
};
```

**option 2**: use the unmanaged variant

```zig
const AnalysisResult = struct {
    findings: std.ArrayListUnmanaged(Finding),

    fn init() AnalysisResult {
        return .{
            .findings = .{},  // Empty initialization
        };
    }

    fn addFinding(self: *AnalysisResult, allocator: std.mem.Allocator, finding: Finding) !void {
        try self.findings.append(allocator, finding);
    }

    fn deinit(self: *AnalysisResult, allocator: std.mem.Allocator) void {
        self.findings.deinit(allocator);
    }
};
```

i went with option 1 for familiarity, but option 2 is more idiomatic in 0.15.

### why this change?

the zig team explains that storing the allocator in the struct adds complexity. with the unmanaged variant as default, you get:
- simpler method signatures
- static initialization support (`.{}`)
- explicit allocator lifetime management

trade-off: you pass the allocator everywhere, but your data structures are cleaner.

## roadblock 2: empty struct initialization `.{}`

**the pattern**: zig 0.15 introduced a shorthand for empty struct initialization.

### what this enables

before, initializing an empty arraylist required:

```zig
var findings = std.ArrayList(Finding).init(allocator);
```

now you can use struct field inference:

```zig
const AnalysisResult = struct {
    findings: std.ArrayList(Finding),

    fn init(allocator: std.mem.Allocator) AnalysisResult {
        return .{
            .findings = .{},  // Compiler infers std.ArrayList(Finding).init(allocator)
            .allocator = allocator,
        };
    }
};
```

this syntax confused me initially because `.{}` looks like an empty struct literal, but it actually calls the appropriate `init` function based on the field type.

**when it works**: field type is clear from context
**when it breaks**: compiler can't infer the type

```zig
var list: std.ArrayList(Item) = .{};  // Works
var list = .{};  // Error: cannot infer type
```

## roadblock 3: process api breaking changes

**the change**: `std.process.Child.run()` return type changed significantly.

### what broke

```zig
fn fetchFromUrl(allocator: std.mem.Allocator, url: []const u8) ![]const u8 {
    const result = try std.process.Child.run(.{
        .allocator = allocator,
        .argv = &[_][]const u8{ "curl", "-fsSL", url },
    });
    defer allocator.free(result.stderr);

    // This line broke
    if (result.term.Exited != 0) {
        allocator.free(result.stdout);
        return error.HttpRequestFailed;
    }

    return result.stdout;
}
```

**error**: `no field named 'Exited' in union 'std.process.Child.Term'`

### the fix

the `term` field changed from having an `Exited` field to being a tagged union:

```zig
fn fetchFromUrl(allocator: std.mem.Allocator, url: []const u8) ![]const u8 {
    const result = try std.process.Child.run(.{
        .allocator = allocator,
        .argv = &[_][]const u8{ "curl", "-fsSL", url },
    });
    defer allocator.free(result.stderr);

    // Check the union variant properly
    switch (result.term) {
        .Exited => |code| {
            if (code != 0) {
                allocator.free(result.stdout);
                return error.HttpRequestFailed;
            }
        },
        else => {
            allocator.free(result.stdout);
            return error.ProcessFailed;
        },
    }

    return result.stdout;
}
```

this is more explicit about handling different termination types (signal, unknown, etc.).

## roadblock 4: http client instability

**the problem**: zig's `std.http.Client` is still evolving rapidly between versions.

### what i tried

```zig
fn fetchFromUrl(allocator: std.mem.Allocator, url: []const u8) ![]const u8 {
    var client = std.http.Client{ .allocator = allocator };
    defer client.deinit();

    const uri = try std.Uri.parse(url);
    var server_header_buffer: [16384]u8 = undefined;

    var req = try client.open(.GET, uri, .{
        .server_header_buffer = &server_header_buffer,
    });
    defer req.deinit();

    try req.send();
    try req.wait();

    // ... read response
}
```

**errors**:
- API mismatches between documentation and actual implementation
- buffer size requirements unclear
- response reading patterns changed between minor versions

### the workaround

the [zig 0.15 release notes](https://ziglang.org/download/0.15.1/release-notes.html) acknowledge: "HTTP client/server completely reworked to depend only on I/O streams, not networking directly."

this instability meant falling back to shelling out:

```zig
fn fetchFromUrl(allocator: std.mem.Allocator, url: []const u8) ![]const u8 {
    // Use curl as a fallback since the Zig HTTP client API is too unstable
    const result = try std.process.Child.run(.{
        .allocator = allocator,
        .argv = &[_][]const u8{ "curl", "-fsSL", url },
    });
    defer allocator.free(result.stderr);

    switch (result.term) {
        .Exited => |code| {
            if (code != 0) {
                allocator.free(result.stdout);
                return error.HttpRequestFailed;
            }
        },
        else => {
            allocator.free(result.stdout);
            return error.ProcessFailed;
        },
    }

    return result.stdout;
}
```

not ideal for a "zero dependency" tool, but pragmatic given the api churn.

## roadblock 5: reader/writer overhaul ("writergate")

**the change**: zig 0.15 completely redesigned `std.io.Reader` and `std.io.Writer` interfaces.

**from the [release notes](https://ziglang.org/download/0.15.1/release-notes.html)**: "A complete overhaul of the standard library Reader and Writer interfaces... designed to usher in a new era of performance and drastically reduce unnecessary copies."

### what changed

**before (0.14)**:
```zig
const stdout = std.io.getStdOut().writer();
try stdout.print("Hello {s}\n", .{"world"});
```

**after (0.15)**:
```zig
const stdout = std.fs.File.stdout();
try stdout.writeAll("Hello world\n");

// For formatted output, you need a buffer
var stdout_buffer: [4096]u8 = undefined;
var stdout_writer = stdout.writer(&stdout_buffer);
try stdout_writer.print("Hello {s}\n", .{"world"});
```

### why this matters

the old api wrapped streams in multiple layers of abstraction. the new api:
- builds buffering directly into reader/writer
- supports zero-copy operations (file-to-file transfers)
- provides precise error sets
- enables vector i/o and advanced operations

but it requires more explicit buffer management.

### my approach

i created a helper function to hide the complexity:

```zig
fn printf(allocator: std.mem.Allocator, comptime fmt: []const u8, args: anytype) !void {
    const stdout = std.fs.File.stdout();
    const msg = try std.fmt.allocPrint(allocator, fmt, args);
    defer allocator.free(msg);
    try stdout.writeAll(msg);
}
```

this allocates for the formatted string, but keeps the call sites clean:

```zig
try printf(allocator, "{s}[{s}]{s} {s}\n", .{
    color_code,
    severity_name,
    Color.NC,
    finding.message
});
```

## roadblock 6: undefined behavior rules tightened

**the change**: zig 0.15 standardizes when `undefined` is allowed.

**from the [release notes](https://ziglang.org/download/0.15.1/release-notes.html)**: "Only operators which can never trigger Illegal Behavior permit undefined as an operand."

### what this means

```zig
// This now errors at compile time
const x: i32 = undefined;
const y = x + 1;  // Error: undefined used in arithmetic

// Safe uses of undefined
var buffer: [256]u8 = undefined;  // OK: just reserves space
const ptr: *u8 = undefined;  // OK: pointers can be undefined
```

this catches bugs earlier but requires more explicit initialization.

### the practical impact

in my code, i couldn't do:

```zig
var line_num: usize = undefined;
while (condition) : (line_num += 1) {  // Error
    // ...
}
```

had to initialize explicitly:

```zig
var line_num: usize = 1;
while (condition) : (line_num += 1) {
    // ...
}
```

## the verdict: worth it?

**what's better in 0.15**:
- 5× faster debug compilation with x86 backend
- clearer allocator lifetime management
- more explicit, less magic
- better performance fundamentals

**what hurts**:
- breaking changes everywhere
- documentation lags behind implementation
- http client still unstable
- community examples are all outdated

## resources

- [zig 0.15.1 release notes](https://ziglang.org/download/0.15.1/release-notes.html) - official breaking changes
- [std.ArrayList documentation](https://ziglang.org/documentation/0.15.1/std/#std.ArrayList) - new allocator patterns
- [safe-curl source code](https://github.com/sngeth/safe-curl-zig) - working 0.15 example
