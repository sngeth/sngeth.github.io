---
layout: post
title: "nanoclaw's memory architecture: sqlite + 200-message rolling window"
date: 2026-03-15
categories: llm agents memory sqlite architecture
excerpt: "a deep dive into nanoclaw's context retrieval mechanism -- no RAG, no embeddings, just SQLite with a cursor-based rolling window and manual tool-based search."
---

---

- [what is nanoclaw](#what-is-nanoclaw)
- [the memory question](#the-memory-question)
- [architecture overview](#architecture-overview)
- [the 200-message rolling window](#the-200-message-rolling-window)
- [cursor-based retrieval mechanism](#cursor-based-retrieval-mechanism)
- [accessing context beyond the window](#accessing-context-beyond-the-window)
- [comparison to RAG-based systems](#comparison-to-rag-based-systems)
- [trade-offs and design decisions](#trade-offs-and-design-decisions)
- [source citations](#source-citations)

---

## what is nanoclaw

nanoclaw is a WhatsApp-integrated AI assistant built on Claude that runs in Docker containers with per-group isolation. it's designed for multi-group conversations with separate memory contexts, scheduled tasks, and persistent message history.

the interesting question isn't what it does -- it's how it manages conversation context across multiple groups with potentially thousands of messages.

## the memory question

when building LLM-based agents, one of the first architectural decisions is: **how do you handle conversation history that exceeds the context window?**

popular approaches:
- **RAG (Retrieval-Augmented Generation)**: embed messages, store in vector DB, retrieve semantically relevant chunks
- **Summarization**: periodically summarize old messages, keep summaries in context
- **Sliding window**: keep last N messages, drop older ones
- **Hybrid**: combine multiple strategies

nanoclaw uses none of these. let's see what it actually does.

## architecture overview

nanoclaw's memory system has two primary components:

1. **SQLite database** (`store/messages.db`) - stores all messages with metadata
2. **Markdown files** (`conversations/` folder) - searchable conversation exports

the database schema is straightforward:

```sql
CREATE TABLE messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_jid TEXT NOT NULL,           -- WhatsApp group ID
  sender TEXT NOT NULL,              -- Phone number
  sender_name TEXT,                  -- Display name
  content TEXT NOT NULL,             -- Message text
  timestamp TEXT NOT NULL,           -- ISO 8601
  is_from_me INTEGER DEFAULT 0,     -- Bot's own messages
  is_bot_message INTEGER DEFAULT 0  -- Messages from bot
);
```

*source: `src/db.ts` lines 15-25*

no embeddings. no vector columns. no fancy indexing beyond the standard B-tree on `chat_jid` and `timestamp`.

## the 200-message rolling window

when nanoclaw processes a new message, it retrieves conversation history using `getMessagesSince()`:

```typescript
export function getMessagesSince(
  chatJid: string,
  sinceTimestamp: string,
  botPrefix: string,
  limit: number = 200,
): NewMessage[] {
  const sql = `
    SELECT * FROM (
      SELECT id, chat_jid, sender, sender_name, content, timestamp, is_from_me
      FROM messages
      WHERE chat_jid = ? AND timestamp > ?
        AND is_bot_message = 0 AND content NOT LIKE ?
        AND content != '' AND content IS NOT NULL
      ORDER BY timestamp DESC
      LIMIT ?
    ) ORDER BY timestamp
  `;
  return db.prepare(sql).all(chatJid, sinceTimestamp, `${botPrefix}:%`, limit);
}
```

*source: `src/db.ts` lines 341-364*

key observations:

1. **Hard limit of 200 messages** - enforced at the SQL level via `LIMIT ?`
2. **Cursor-based pagination** - uses `sinceTimestamp` instead of fixed time window
3. **Chronological order** - `ORDER BY timestamp` ensures messages are in conversation order
4. **Filters bot's own messages** - excludes `is_bot_message = 1` to avoid self-references

the 200-message limit is **not configurable** and **not adaptive** based on token count. it's a simple message count cap.

## cursor-based retrieval mechanism

the "rolling window" isn't time-based -- it's **cursor-based**. here's how it works:

```typescript
// src/index.ts lines 158-163
const sinceTimestamp = lastAgentTimestamp[chatJid] || '';
const missedMessages = getMessagesSince(chatJid, sinceTimestamp, ASSISTANT_NAME);

// After processing...
// src/index.ts lines 183-184
lastAgentTimestamp[chatJid] = missedMessages[missedMessages.length - 1].timestamp;
```

**flow:**

1. **Initial state**: `lastAgentTimestamp` is empty string `''`
   - retrieves last 200 messages from entire history
2. **After first run**: cursor advances to timestamp of last processed message
3. **Next run**: retrieves all messages AFTER that timestamp (up to 200)
4. **If < 200 new messages**: gets all of them
5. **If > 200 new messages**: gets only 200 most recent, **older ones are dropped**

**this means:**
- if you send 500 messages while the bot is offline, it only sees the last 200
- the cursor never goes backward
- there's no "lookback" or "re-retrieval" of older context

## accessing context beyond the window

so what happens if you reference something from message #201?

nanoclaw provides **manual retrieval tools**:

### 1. conversation folder exports

```markdown
# conversations/
The `conversations/` folder contains searchable history of
past conversations. Use this to recall context from previous sessions.
```

*source: `groups/main/CLAUDE.md` line 39*

agents can use the `Read` tool to read exported conversation markdown files.

### 2. grep tool

agents can search message content using the `Grep` tool:

```typescript
Grep({
  pattern: "budget discussion",
  path: "/workspace/project/conversations/",
  output_mode: "content"
})
```

### 3. direct database queries

agents can query the SQLite database directly via `Bash` tool:

```bash
sqlite3 /workspace/project/store/messages.db "
  SELECT timestamp, sender_name, content
  FROM messages
  WHERE chat_jid = '120363336345536173@g.us'
    AND content LIKE '%budget%'
  ORDER BY timestamp DESC
  LIMIT 10;
"
```

**key point**: retrieval is **manual** and **tool-initiated**. the agent must explicitly decide to search for old context. it's not automatic like RAG.

## comparison to RAG-based systems

| feature | nanoclaw | typical RAG system |
|---------|----------|-------------------|
| **storage** | SQLite (relational) | Vector DB (Pinecone, Chroma, Weaviate) |
| **retrieval** | manual tool calls | automatic semantic search |
| **context selection** | chronological (last 200) | semantic similarity top-k |
| **embeddings** | none | required |
| **search** | SQL WHERE / Grep | vector similarity (cosine, euclidean) |
| **latency** | sub-millisecond SQL | depends on vector DB, usually 10-100ms |
| **cost** | zero (SQLite is free) | vector DB hosting + embedding API calls |
| **complexity** | low (just SQL) | medium-high (embedding pipeline, vector indexing) |

**why this matters:**

RAG systems automatically retrieve relevant context based on semantic similarity:
- user asks "what was our budget discussion?"
- system embeds the query
- retrieves top 5 semantically similar messages
- adds them to context

nanoclaw requires the agent to **explicitly search**:
- agent sees "what was our budget discussion?"
- agent thinks "I need to search for this"
- agent calls `Grep` or `Read` tool
- agent adds findings to response

this is **more transparent** (you see the search happening) but **less automatic** (agent might forget to search).

## trade-offs and design decisions

### why 200 messages?

likely a balance between:
- **context window limits**: keeping token count manageable
- **conversation coherence**: 200 messages covers most multi-turn conversations
- **query performance**: SQLite `LIMIT 200` is fast even on large tables

### why no embeddings?

embeddings add complexity:
- need embedding API (OpenAI, Cohere, etc.) or local model
- need vector storage and indexing
- need embedding refresh on message updates
- adds latency and cost

for a personal assistant handling dozens of groups, **simplicity > sophistication**.

### why cursor-based?

alternatives:
- **time window** (last 7 days): breaks if conversation is inactive for a week
- **fixed offset** (messages 1000-1200): doesn't adapt to conversation growth
- **cursor** (since last processed): always picks up where you left off

cursor-based ensures **continuity** even with irregular message patterns.

### why manual retrieval?

automatic RAG retrieval can:
- add irrelevant context (semantic similarity isn't perfect)
- increase latency (every message triggers vector search)
- use more tokens (retrieved chunks added to every request)

manual retrieval gives the agent **control** over when to pay the cost of searching.

## source citations

all analysis based on nanoclaw repository source code:

1. **database schema**: `src/db.ts` lines 15-25
2. **getMessagesSince function**: `src/db.ts` lines 341-364
3. **cursor advancement**: `src/index.ts` lines 158-163, 183-184
4. **conversation folder docs**: `groups/main/CLAUDE.md` line 39
5. **message filtering**: excludes `is_bot_message` and bot-prefixed content

---

**bottom line**: nanoclaw's memory is **simple by design**. no embeddings, no RAG, just SQLite with a 200-message rolling window and manual tool-based search. it trades automatic semantic retrieval for simplicity, transparency, and zero external dependencies.

for a multi-group WhatsApp assistant, that's probably the right call.
