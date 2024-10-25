---
layout: post
title: "Database Indexes"
category: "Databases"
comments: true
---

## Why This Interview Question Needs a Rethink

Software companies frequently ask about database indexing during interviews, which might seem puzzling given that complexity analysis can be easily googled. Even more puzzling: if the goal is to assess system design knowledge, why not directly ask about specific scaling challenges or data access patterns?

The truth is, this question often reveals more about the interviewer's habits than their assessment goals. A better line of questioning might be:

- "What read/write patterns in your current system influenced your indexing strategy?"
- "How did you determine when to add or remove indexes in production?"
- "What monitoring helped you identify index-related performance issues?"

These questions would better reveal an engineer's practical experience with database performance tuning. Nevertheless, let's explore both the theoretical foundations and real-world implications that make index knowledge crucial for day-to-day engineering decisions.

## The Theoretical Foundation

### Complexity Analysis

Without an index (sequential scan):
- Time complexity: O(n) where n is the number of rows
- Every row must be examined to find matches
- Optimal for scanning large portions of the table (>15-20% of rows)

With a B-tree index:
- Time complexity: O(log n) for lookups, inserts, and deletes
- B-tree height typically remains 2-4 levels even with millions of rows
- Each level requires one disk I/O operation
- Ideal for highly selective queries

Consider a table with 1,000,000 rows:
- Sequential scan requires checking all 1,000,000 rows
- B-tree index typically needs only 3-4 lookups

## Inside a B-tree Index: A Practical Example

Understanding how B-tree indexes actually work helps explain both their performance characteristics and limitations. Let's walk through a concrete example.

### B-tree Structure

Consider a table of users with an index on the `age` column:

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name TEXT,
    age INTEGER,
    email TEXT
);

CREATE INDEX idx_users_age ON users(age);
```

The resulting B-tree structure might look like this:

```
Root Node (Level 0)
[20, 40, 60]
 |   |   |   |
 v   v   v   v
Level 1 Nodes
[10,15] [25,30,35] [45,50,55] [70,80,90]
 |  |  |  |  |  |  |  |  |   |  |  |
 v  v  v  v  v  v  v  v  v   v  v  v
Leaf Nodes (Level 2)
[Pointers to actual table rows...]
```

### How Lookups Work

Let's trace what happens when we execute:
```sql
SELECT * FROM users WHERE age = 25;
```

1. **Root Node Traversal**
   ```python
   def find_in_node(node, target):
       # Binary search within node's keys
       for i, key in enumerate(node.keys):
           if target < key:
               return node.children[i]
           elif target == key:
               return node.children[i + 1]
       return node.children[-1]

   def btree_search(root, target):
       current = root
       while not current.is_leaf:
           current = find_in_node(current, target)
   ```

2. **Leaf Node Access**
   ```python
   class LeafNode:
       def __init__(self):
           self.keys = []  # The indexed values
           self.row_pointers = []  # Pointers to actual table rows
           self.next_leaf = None  # For range scans

   def get_row_pointers(leaf_node, target):
       matches = []
       for i, key in enumerate(leaf_node.keys):
           if key == target:
               matches.append(leaf_node.row_pointers[i])
       return matches
   ```

### Insert Operations

When inserting a new record:

```python
def insert(root, key, row_pointer):
    # Find the appropriate leaf node
    leaf = find_leaf_node(root, key)

    # If leaf has space, simply insert
    if len(leaf.keys) < MAX_KEYS:
        insert_in_leaf(leaf, key, row_pointer)
        return root

    # Otherwise, split the node
    new_leaf = split_leaf(leaf, key, row_pointer)

    # Propagate the split upward if necessary
    return propagate_split(root, leaf, new_leaf)
```

## The Real-World Impact

This is where theoretical knowledge transforms into practical engineering decisions. Here's what actually happens in production systems:

### Write Performance Impact

1. **Single Record Operations**
   - Base insert without index: ~1ms
   - Each additional index adds: ~2-10ms overhead
   - Impact: 4-5 indexes can make inserts 3-5x slower

2. **Bulk Operations**
   - 1M row import with no indexes: ~2-3 minutes
   - Same import with 3 indexes: ~5-8 minutes
   - With 5+ indexes: Can extend to 15+ minutes or more

### When It Really Hurts

The performance impact becomes particularly noticeable in:

1. **High-frequency Insert Systems**
   - Logging systems
   - Real-time data pipelines
   - IoT data collection
   - High-volume transaction systems

2. **Development Pain Points**
   - Adding "just one more index" suddenly making writes noticeably slower
   - Background index creation blocking production writes
   - Unexpected storage growth (each index can add 20-30% to table size)

## Making the Right Engineering Decisions

Understanding both theoretical and practical aspects helps engineers make better decisions:

1. **Index Strategically**
   - Don't index everything that could be queried
   - Consider query-to-write ratio for each table
   - Monitor index usage and remove unused indexes

2. **Balance Performance Tradeoffs**
   - Accept slower writes for critical read performance
   - Consider partial indexes for large tables
   - Use covering indexes for crucial queries

3. **Plan for Scale**
   - Anticipate growth in both data volume and query patterns
   - Consider index maintenance windows
   - Monitor index bloat and performance degradation

## Conclusion

While understanding B-tree complexity is important, the real engineering value comes from:
1. Recognizing specific access patterns in your system
2. Understanding the concrete performance implications
3. Making informed tradeoffs based on actual requirements

The next time you're interviewing candidates, consider skipping the theoretical complexity question. Instead, ask about their experience with real database performance challenges and how they measured, monitored, and resolved them. These answers will tell you far more about their engineering capabilities than whether they can recite trivia knowledge.
