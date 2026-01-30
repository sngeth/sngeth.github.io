---
layout: post
title: "server-side vs client-side tools in llm apis"
date: 2026-01-30
categories: ai llm anthropic api-design
---

when building agentic applications with the anthropic api, understanding the difference between client tools and server tools is essential. they have different execution models, response structures, and handling requirements.

## the two types of tools

from the [anthropic documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use):

> Claude supports two types of tools:
>
> 1. **Client tools**: Tools that execute on your systems
> 2. **Server tools**: Tools that execute on Anthropic's servers, like the web search and web fetch tools. These tools must be specified in the API request but don't require implementation on your part.

| aspect | client tools | server tools |
|--------|--------------|--------------|
| execution | your systems | anthropic's servers |
| response handling | you must return `tool_result` | results arrive automatically |
| content blocks | `tool_use` | `server_tool_use` + `web_search_tool_result` |
| definition | `input_schema` object | versioned `type` field |

## defining each type

**client tool** - you provide a schema, claude generates input, you execute it:

```typescript
{
  name: "get_weather",
  description: "Get the current weather in a given location",
  input_schema: {
    type: "object",
    properties: {
      location: {
        type: "string",
        description: "The city and state, e.g. San Francisco, CA"
      }
    },
    required: ["location"]
  }
}
```

**server tool** - you specify a versioned type, anthropic handles execution:

```typescript
{
  type: "web_search_20250305",
  name: "web_search",
  max_uses: 5
}
```

server tools use versioned types (e.g., `web_search_20250305`) to ensure compatibility across model versions.

## different workflows

### client tool workflow

1. you define the tool with a schema
2. claude returns a `tool_use` block with `stop_reason: "tool_use"`
3. **you execute the tool on your systems**
4. **you return results via `tool_result`**
5. claude formulates the final response

```typescript
// client tool response
{
  "stop_reason": "tool_use",
  "content": [
    {
      "type": "tool_use",
      "id": "toolu_01A09q90qw90lq917835lq9",
      "name": "get_weather",
      "input": {"location": "San Francisco, CA"}
    }
  ]
}
```

you then execute and return:

```typescript
messages.push({
  role: "user",
  content: [{
    type: "tool_result",
    tool_use_id: "toolu_01A09q90qw90lq917835lq9",
    content: "72°F, sunny"
  }]
});
```

### server tool workflow

1. you specify the server tool in your request
2. claude executes the tool automatically
3. **results are embedded in the response** as `web_search_tool_result`
4. **no `tool_result` needed from you**
5. claude formulates the final response

```typescript
// server tool response
{
  "content": [
    {
      "type": "text",
      "text": "I'll search for that information."
    },
    {
      "type": "server_tool_use",
      "id": "srvtoolu_01WYG3ziw53XMcoyKL4XcZmE",
      "name": "web_search",
      "input": { "query": "claude shannon birth date" }
    },
    {
      "type": "web_search_tool_result",
      "tool_use_id": "srvtoolu_01WYG3ziw53XMcoyKL4XcZmE",
      "content": [
        {
          "type": "web_search_result",
          "url": "https://en.wikipedia.org/wiki/Claude_Shannon",
          "title": "Claude Shannon - Wikipedia",
          "encrypted_content": "..."
        }
      ]
    },
    {
      "type": "text",
      "text": "Claude Shannon was born on April 30, 1916...",
      "citations": [...]
    }
  ]
}
```

the key difference: **server tool results are already in the response**. anthropic executed the search; you just continue the conversation.

## handling both in an agentic loop

when building an agentic loop that uses both tool types, you need to distinguish between them:

```typescript
if (response.stop_reason === "tool_use") {
  messages.push({ role: "assistant", content: response.content });

  // find client-side tools that need results
  const clientToolBlocks = response.content.filter(
    (block): block is Anthropic.ToolUseBlock =>
      block.type === "tool_use"
  );

  if (clientToolBlocks.length > 0) {
    // execute client tools and return results
    const toolResults: Anthropic.ToolResultBlockParam[] = [];
    for (const block of clientToolBlocks) {
      const result = await executeMyTool(block.name, block.input);
      toolResults.push({
        type: "tool_result",
        tool_use_id: block.id,
        content: result,
      });
    }
    messages.push({ role: "user", content: toolResults });
  }
}

// for server tools, check for server_tool_use blocks
const hasServerTool = response.content.some(
  block => block.type === "server_tool_use"
);
```

the `server_tool_use` block type tells you anthropic is handling execution. the results come back as `web_search_tool_result` blocks in the same response.

## common mistake: sending empty tool_result for server tools

a common bug is treating server tools like client tools:

```typescript
// wrong: sending tool_result for server-side tools
for (const block of response.content) {
  if (block.type === "tool_use") {
    toolResults.push({
      type: "tool_result",
      tool_use_id: block.id,
      content: "",  // what would you even put here?
    });
  }
}
```

this happens when code is adapted from client-tool examples without accounting for server tools. sending empty `tool_result` messages injects noise into the conversation - the model may interpret it as the tool failing.

## pricing

server tools have usage-based pricing in addition to token costs. from the [web search documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-search-tool):

> Web search is available on the Claude API for **$10 per 1,000 searches**, plus standard token costs for search-generated content.

the usage is tracked in the response:

```json
"usage": {
  "input_tokens": 105,
  "output_tokens": 6039,
  "server_tool_use": {
    "web_search_requests": 1
  }
}
```

## key points

- **client tools**: you define, you execute, you return `tool_result`
- **server tools**: you specify, anthropic executes, results arrive automatically
- **detect by block type**: `tool_use` vs `server_tool_use`
- **never send `tool_result` for server tools** - the results are already in the response
- **server tools are versioned** (e.g., `web_search_20250305`) for compatibility

## references

- [tool use with claude](https://docs.anthropic.com/en/docs/build-with-claude/tool-use) - official documentation
- [web search tool](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-search-tool) - server tool example with pricing
