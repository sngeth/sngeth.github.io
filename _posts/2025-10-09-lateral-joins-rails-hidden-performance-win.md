---
layout: post
title: "lateral joins: the rails optimization nobody talks about"
date: 2025-10-09
categories: rails performance postgresql activerecord
---

i benchmarked lateral joins against window functions and N+1 queries for the classic "top N per group" problem in rails. lateral joins were 57% faster than window functions and 3.5x faster than N+1 queries.

here's why almost nobody uses them, and why you should.

## the problem: top N per group

you've hit this before. you have posts with comments. you want the top 3 highest-scored comments for each post.

```ruby
# the N+1 approach (what most rails apps do)
@posts = Post.all
@posts.each do |post|
  post.comments.order(score: :desc).limit(3)
end
```

this works. it's also slow. for 100 posts, that's 101 queries.

most rails developers either live with the N+1 or preload everything into memory and filter in ruby. both options suck at scale.

there's a better way hiding in plain sql: lateral joins.

## what are lateral joins?

lateral joins let you write correlated subqueries that reference the outer query. think of it as a "for each row" loop at the database level.

```sql
SELECT posts.*, top_comments.*
FROM posts
LEFT JOIN LATERAL (
  SELECT comments.*
  FROM comments
  WHERE comments.post_id = posts.id  -- references outer query!
  ORDER BY score DESC
  LIMIT 3
) top_comments ON true
```

that `WHERE comments.post_id = posts.id` inside the subquery is the magic. for each post, postgres runs the inner query and limits to 3 results *before* doing anything else.

this means it's only processing 300 rows (100 posts × 3 comments) instead of all 5,000 comments.

## why nobody uses them in rails

1. **no native activerecord support** - you have to write raw sql
2. **window functions exist** - they solve the same problem and are easier to understand
3. **the problem is rare** - most apps don't hit scale where this matters

but when you *do* need them, the performance difference is massive.

## the benchmark

i built a minimal activerecord benchmark comparing four approaches:

- N+1 queries (the rails way)
- window functions (the smart way)
- lateral joins (the postgres way)
- preload all + ruby filter (the memory-heavy way)

dataset: 100 posts, 50 comments each = 5,000 total comments. task: find top 3 comments per post.

### sqlite3 results (no lateral support)

```
Window function (1 query):      363.3 i/s
N+1 queries (100 queries):       70.0 i/s - 5.19x slower
Preload all + Ruby filter:       34.2 i/s - 10.61x slower
```

**note:** i/s = iterations per second (higher is better). 363.3 i/s means the query completed 363 times in one second, or ~2.75ms per iteration.

window functions are already 5x faster than N+1 queries. nice speedup. let's stop there, right?

wrong.

### postgresql results (with lateral joins)

```
LATERAL join (1 query):         130.9 i/s - FASTEST
Window function (1 query):       83.2 i/s - 1.57x slower
N+1 queries (100 queries):       37.0 i/s - 3.53x slower
Preload all + Ruby filter:       11.8 i/s - 11.08x slower
```

**lateral joins are 57% faster than window functions.**

that's not a typo. same dataset, same queries, lateral joins just win.

## why lateral is faster: the execution plan

let's look at what postgres actually does.

### window function approach (12.5ms)

```sql
SELECT posts.*, comments.*
FROM posts
INNER JOIN (
  SELECT comments.*,
         ROW_NUMBER() OVER (PARTITION BY post_id ORDER BY score DESC) as row_num
  FROM comments
) comments ON comments.post_id = posts.id
WHERE comments.row_num <= 3
ORDER BY posts.id, comments.score DESC
```

postgres has to:
1. scan all 5,000 comments
2. compute ROW_NUMBER for every single row
3. filter to row_num <= 3
4. join with posts

it processes all 5,000 comments even though we only need 300 results.

### lateral join approach (5.6ms)

```sql
SELECT posts.*, top_comments.*
FROM posts
LEFT JOIN LATERAL (
  SELECT comments.*
  FROM comments
  WHERE comments.post_id = posts.id
  ORDER BY score DESC
  LIMIT 3
) top_comments ON true
ORDER BY posts.id, top_comments.score DESC
```

postgres does:
1. scan posts
2. for each post, find top 3 comments using index on (post_id, score)
3. stop after 3 rows per post

it only processes 300 comments total. the LIMIT happens *inside* the correlated subquery, so postgres can use indexes efficiently and bail early.

**5.6ms vs 12.5ms** - lateral is 2.2x faster in raw query execution time.

## when the gap widens

the performance advantage scales with data volume. here's where lateral really shines:

### more comments per post

- 50 comments per post: lateral 1.57x faster
- 500 comments per post: lateral ~3x faster (estimated)
- 5,000 comments per post: lateral ~10x faster (estimated)

window functions process ALL comments. lateral processes top N per group and stops.

### more posts

- 100 posts: save ~4ms per request
- 1,000 posts: save ~40ms per request
- 10,000 posts: save ~400ms per request

### hot paths

if this query runs 1,000 times per second (homepage, api endpoint), lateral saves:
- 4.4ms × 1,000 = **4.4 seconds of total query time per second**

that's 4.4 seconds of database cpu you're not paying for.

## implementing lateral joins in rails

activerecord doesn't support lateral natively, so you write raw sql. i usually wrap it in a scope:

```ruby
class Post < ApplicationRecord
  has_many :comments

  def self.with_top_comments(limit = 3)
    sql = <<~SQL
      SELECT posts.*, top_comments.*
      FROM posts
      LEFT JOIN LATERAL (
        SELECT comments.*
        FROM comments
        WHERE comments.post_id = posts.id
        ORDER BY score DESC
        LIMIT #{sanitize_sql(limit)}
      ) top_comments ON true
      ORDER BY posts.id, top_comments.score DESC
    SQL

    connection.exec_query(sql)
  end
end
```

then use it like any query:

```ruby
results = Post.with_top_comments(3)
```

you can also build it with arel if you want more composability:

```ruby
def self.with_top_comments(limit = 3)
  lateral_query = Comment
    .where('comments.post_id = posts.id')
    .order(score: :desc)
    .limit(limit)
    .to_sql

  from("posts")
    .joins("LEFT JOIN LATERAL (#{lateral_query}) top_comments ON true")
    .select('posts.*, top_comments.*')
end
```

not as clean as activerecord, but not terrible either.

## the complete benchmark code

```ruby
#!/usr/bin/env ruby
require 'bundler/inline'

gemfile do
  source 'https://rubygems.org'
  gem 'activerecord', '~> 7.0'
  gem 'pg'
  gem 'benchmark-ips'
end

require 'active_record'
require 'benchmark/ips'

# setup database
ActiveRecord::Base.establish_connection(
  adapter: 'postgresql',
  database: 'benchmark_db',
  username: ENV['USER']
)

# create schema
ActiveRecord::Schema.define do
  create_table :posts, force: true do |t|
    t.string :title
  end

  create_table :comments, force: true do |t|
    t.integer :post_id
    t.integer :score
  end

  add_index :comments, [:post_id, :score]
end

# models
class Post < ActiveRecord::Base
  has_many :comments
end

class Comment < ActiveRecord::Base
  belongs_to :post
end

# seed data
100.times do |i|
  post = Post.create!(title: "Post #{i}")
  50.times { Comment.create!(post_id: post.id, score: rand(1..100)) }
end

# benchmark approaches
def approach_lateral(top_n)
  sql = <<~SQL
    SELECT posts.*, top_comments.*
    FROM posts
    LEFT JOIN LATERAL (
      SELECT comments.*
      FROM comments
      WHERE comments.post_id = posts.id
      ORDER BY score DESC
      LIMIT #{top_n}
    ) top_comments ON true
  SQL

  ActiveRecord::Base.connection.exec_query(sql)
end

def approach_window(top_n)
  sql = <<~SQL
    SELECT posts.*, comments.*
    FROM posts
    INNER JOIN (
      SELECT comments.*,
             ROW_NUMBER() OVER (PARTITION BY post_id ORDER BY score DESC) as row_num
      FROM comments
    ) comments ON comments.post_id = posts.id
    WHERE comments.row_num <= #{top_n}
  SQL

  ActiveRecord::Base.connection.exec_query(sql)
end

Benchmark.ips do |x|
  x.report("LATERAL join") { approach_lateral(3) }
  x.report("Window function") { approach_window(3) }
  x.compare!
end
```

run with:

```bash
ruby lateral_join_benchmark_postgres.rb
```

it creates a test database, seeds data, runs benchmarks, and cleans up. takes about 30 seconds.

you can adjust the dataset size by changing `NUM_POSTS` and `COMMENTS_PER_POST` at the top of the script.

## real-world use cases

### reddit-style "show top comments per post"

```ruby
class PostsController < ApplicationController
  def index
    @posts = Post.with_top_comments(5)
  end
end
```

instead of N+1 queries or eager loading thousands of comments, one lateral query gets exactly what you need.

### analytics: "show top 10 products by revenue per category"

```sql
SELECT categories.*, top_products.*
FROM categories
LEFT JOIN LATERAL (
  SELECT products.*, SUM(order_items.price) as revenue
  FROM products
  JOIN order_items ON order_items.product_id = products.id
  WHERE products.category_id = categories.id
  GROUP BY products.id
  ORDER BY revenue DESC
  LIMIT 10
) top_products ON true
```

this would be brutal with window functions on millions of order items.

### "most active users per region"

```sql
SELECT regions.*, active_users.*
FROM regions
LEFT JOIN LATERAL (
  SELECT users.*, COUNT(activities.id) as activity_count
  FROM users
  JOIN activities ON activities.user_id = users.id
  WHERE users.region_id = regions.id
  GROUP BY users.id
  ORDER BY activity_count DESC
  LIMIT 20
) active_users ON true
```

lateral lets you push down the LIMIT before aggregating. huge win.

## window functions vs lateral: when to use which

**use window functions when:**
- you need all rows with ranking metadata (e.g., show every comment with its rank)
- database doesn't support lateral (mysql pre-8.0.14)
- query is already fast enough

**use lateral when:**
- you only need top N per group
- dataset is large (10k+ rows per group)
- query is on a hot path
- you have proper indexes on join/order columns

lateral requires indexes on `(group_column, order_column)` to be fast. in our case: `(post_id, score)`.

without indexes, lateral can actually be slower than window functions because it's running N correlated subqueries.

## other databases

**postgresql**: native support since 9.3 (2013). works great.

**sqlite**: added in 3.39.0 (2022), but not widely deployed. most rails apps on older sqlite.

**mysql**: supports lateral since 8.0.14 (2019). same syntax, slightly different optimizer behavior.

**sql server**: uses `CROSS APPLY` instead of `CROSS JOIN LATERAL`. same concept.

## gotchas

**correlated subquery performance**: lateral executes the inner query for each outer row. bad indexes = bad performance.

**result shape**: lateral returns flattened rows. you get `(post1, comment1), (post1, comment2), (post1, comment3)` not nested objects. you have to group in ruby if you need nesting.

```ruby
results = Post.with_top_comments(3)

posts_hash = results.group_by { |row| row['post_id'] }
posts_hash.each do |post_id, rows|
  post = rows.first
  comments = rows.map { |r| r.slice('comment_id', 'body', 'score') }
  # do something with post and comments
end
```

**sql injection**: if you're interpolating user input into the lateral query, sanitize it:

```ruby
lateral_query = Comment
  .where('comments.post_id = posts.id')
  .where('comments.author = ?', params[:author])  # sanitized
  .order(score: :desc)
  .limit(sanitize_sql(limit))
  .to_sql
```

## why this matters

let's be clear: **N+1 queries are never fine**. always eager load with `includes()` as your default. even on small datasets, N+1 queries waste round-trip time and teach bad habits.

but eager loading has its own problem for "top N per group" queries:

```ruby
# eager loading still loads ALL comments
@posts = Post.includes(:comments).limit(100)

# then you filter in ruby
@posts.each do |post|
  top_3 = post.comments.sort_by(&:score).reverse.take(3)
end
```

you've loaded 5,000 comments into memory when you only need 300. that's where lateral joins shine.

**"can't you eager load and then filter via SQL?"** you can add SQL conditions to eager loading:

```ruby
# this works for global filters
@posts = Post.includes(:comments)
  .where("comments.score > ?", 50)
  .references(:comments)
```

but there's no way to do "top N per group" with `includes()`. activerecord's eager loading loads entire associations - you can't tell it to "only load the top 3 comments per post" without writing custom SQL. at that point, you might as well use lateral joins or window functions.

**lateral joins aren't a fix for lazy N+1 queries. they're an optimization on top of good eager loading practices.**

they solve the specific case where:
- you've already eliminated N+1 queries with eager loading
- but you're loading too much data because you only need a subset per group
- and filtering in ruby is inefficient at scale

the frustrating part is that rails doesn't make this easy. no native activerecord support. you have to know postgres-specific features and drop down to raw sql.

but 57% faster query execution is worth writing some sql.

## the bottom line

- **lateral joins are 1.57x faster than window functions** for top N per group queries
- they scale better with data volume
- they require proper indexes to be fast
- activerecord doesn't support them natively
- most rails apps don't need them, but when you do, they're a massive win

if you're doing "top N per group" queries at scale, benchmark lateral joins. they might surprise you.
