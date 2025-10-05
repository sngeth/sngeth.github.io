---
layout: post
title: "materialized views made my dashboard 9000x faster"
date: 2025-10-03
categories: rails performance postgresql
---

i built a rails dashboard to analyze millions of records. first pass: painfully slow. adding materialized views with the scenic gem: absurdly fast.

here's what i learned benchmarking against 100k users, 1M orders, and 5M user activities.

## the problem

dashboard queries were hitting multiple tables with joins and aggregations. every page load meant scanning millions of rows, grouping, sorting... you know the drill.

daily sales query: 7.1 seconds per request. user engagement: same pain. this is fine for batch reports but unusable for a dashboard people actually look at.

## materialized views in 30 seconds

regular views are just saved queries. postgres re-runs them every time.

materialized views are snapshots. postgres runs the query once, stores the results as a real table. subsequent reads? just SELECT from that cached table.

trade-off: data gets stale until you refresh. for dashboards where 5-60 minute staleness is fine, this works great.

## scenic gem setup

scenic wraps postgres materialized views in rails migrations. feels native.

```bash
rails generate scenic:view daily_sales
```

creates two files:
- migration file to create the view
- sql file for your query

here's the daily sales view:

```sql
SELECT
  DATE(orders.order_date) AS sale_date,
  COUNT(DISTINCT orders.id) AS total_orders,
  COUNT(DISTINCT orders.user_id) AS unique_customers,
  SUM(orders.total_amount) AS total_revenue,
  AVG(orders.total_amount) AS average_order_value,
  SUM(CASE WHEN orders.status = 'completed' THEN 1 ELSE 0 END) AS completed_orders,
  SUM(CASE WHEN orders.status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_orders
FROM orders
GROUP BY DATE(orders.order_date)
ORDER BY sale_date DESC
```

normal complex aggregation. but instead of running this every time, we materialize it:

```ruby
class CreateDailySales < ActiveRecord::Migration[8.0]
  def change
    create_view :daily_sales, materialized: true
    add_index :daily_sales, :sale_date, unique: true
  end
end
```

now you can query it like any rails model:

```ruby
class DailySale < ApplicationRecord
  def readonly?
    true
  end

  def self.refresh
    Scenic.database.refresh_materialized_view(table_name, concurrently: false, cascade: false)
  end
end

# in your controller
@daily_sales = DailySale.order(sale_date: :desc).limit(30)
```

postgres reads from a pre-computed table instead of scanning orders every time.

## the benchmarks

i built 4 materialized views:
1. daily_sales - revenue metrics by day
2. top_products - product performance
3. user_engagements - customer lifetime value
4. category_revenues - category breakdowns

then benchmarked raw queries vs materialized views using benchmark-ips.

### results

**daily sales summary**
- raw query: 6.25 iterations/sec (160ms per query)
- materialized view: 2,191 iterations/sec (456 microseconds per query)
- **350x faster**

**top products by revenue**
- raw query: 0.69 iterations/sec (1.44 seconds per query)
- materialized view: 438 iterations/sec (2.28ms per query)
- **633x faster**

**user engagement metrics**
- raw query: 0.14 iterations/sec (7.12 seconds per query)
- materialized view: 135 iterations/sec (7.39ms per query)
- **963x faster**

**category revenue analysis**
- raw query: 0.29 iterations/sec (3.41 seconds per query)
- materialized view: 2,715 iterations/sec (368 microseconds per query)
- **9,252x faster**

the user engagement query went from 7 seconds to 7 milliseconds. category revenue from 3.4 seconds to 368 microseconds.

## how the queries work

let's look at the user engagement view since it had the biggest pain:

```sql
SELECT
  users.id AS user_id,
  users.email,
  users.name,
  COUNT(DISTINCT orders.id) AS total_orders,
  SUM(orders.total_amount) AS lifetime_value,
  AVG(orders.total_amount) AS avg_order_value,
  COUNT(DISTINCT user_activities.id) AS total_activities,
  COUNT(DISTINCT CASE WHEN user_activities.activity_type = 'page_view' THEN user_activities.id END) AS page_views,
  MAX(orders.order_date) AS last_order_date,
  MAX(user_activities.occurred_at) AS last_activity_date,
  DATE_PART('day', NOW() - MAX(user_activities.occurred_at)) AS days_since_last_activity
FROM users
LEFT JOIN orders ON users.id = orders.user_id
LEFT JOIN user_activities ON users.id = user_activities.user_id
GROUP BY users.id, users.email, users.name
ORDER BY lifetime_value DESC NULLS LAST
```

two left joins across 100k users, 1M orders, and 5M activities. grouping, aggregating, sorting. every single time someone loads the dashboard.

materialized it? 100k rows pre-computed. SELECT with a simple ORDER BY and LIMIT.

the indexes matter too:

```ruby
add_index :user_engagements, :user_id, unique: true
```

postgres can use the index for lookups. filtering by high-value customers? instant.

## why materialized views are faster: database internals

ran `EXPLAIN ANALYZE` on both approaches to see what postgres is actually doing. the difference is wild.

### raw query execution (7.1 seconds)

```
Limit  (cost=1666565.79..1666566.04 rows=100)
  Buffers: shared hit=383450 read=135233 written=1559
  ->  Sort  (top-N heapsort)
        ->  GroupAggregate  (rows=100000)
              ->  Merge Left Join  (rows=50455739)  ← 50 MILLION intermediate rows
                    ->  Gather Merge (parallel workers: 2)
                          ->  Incremental Sort
                                ->  Merge Left Join (users + orders)
                    ->  Materialize (user_activities, 5M rows)
```

what's happening:
- joins 100k users + 1M orders + 5M activities
- creates **50 million intermediate rows**
- groups all 100k users
- sorts by lifetime value
- reads **135,233 disk blocks** from storage
- takes top 100

the query is scanning millions of rows, doing complex joins, aggregating, then sorting. postgres is working hard.

### materialized view execution (7.4ms)

```
Limit  (cost=0.29..8.87 rows=100)
  Buffers: shared hit=103
  ->  Index Scan using index_user_engagements_on_user_id
        Order By: lifetime_value DESC
```

what's happening:
- uses index to read rows sorted by lifetime_value
- reads **103 blocks** (all from cache)
- stops after 100 rows

no joins. no aggregation. no sorting. just reading pre-computed results.

### buffer analysis: cache hits matter

postgres tracks how often data is read from RAM (cache hits) vs disk:

**base tables getting hammered by raw queries:**
```
order_items:      5.2M disk reads, 76% cache hit ❌
user_activities:  1.3M disk reads, 91% cache hit ❌
orders:           817K disk reads, 95% cache hit ⚠️
```

**materialized views:**
```
daily_sales:        37 disk reads, 99.88% cache hit ✅
user_engagements: 9,612 disk reads, 99.71% cache hit ✅
top_products:     1,168 disk reads, 99.87% cache hit ✅
```

disk reads are ~1000x slower than RAM. materialized views stay in cache because they're small and accessed frequently.

### query cost comparison

postgres estimates query cost before execution:

| query | raw cost | view cost | ratio |
|-------|----------|-----------|-------|
| daily sales | 101,503 | 0.96 | 105,628x |
| user engagement | 763,318 | 2.86 | 266,860x |
| top products | 101,996 | 2.54 | 40,156x |

these aren't execution times, they're cost units. includes disk I/O, CPU operations, memory usage. lower is better.

raw query for user engagement costs **763,318 units**. materialized view: **2.86 units**.

### the memory problem: external sorts

raw daily sales query execution plan shows this:

```
Sort Method: external merge  Disk: 14208kB
  Worker 0: Disk: 12200kB
  Worker 1: Disk: 13736kB
```

sorting 1M rows doesn't fit in `work_mem`, so postgres spills to disk. writes ~40MB of temporary files across 3 parallel workers.

disk I/O during sorting kills performance.

materialized views? no sorting needed. data is already sorted via indexes.

### sequential scans vs index scans

checked how often postgres uses indexes vs scanning entire tables:

**base tables:**
```
orders:      5.5M index scans (99.99% index usage) ✅
users:       6.2M index scans (100% index usage)   ✅
products:    7.0M index scans (100% index usage)   ✅
```

every raw query hits these tables with index lookups. millions of operations putting load on the database.

**materialized views:**
```
category_revenues: 38,642 sequential scans (0 index scans) ✅
top_products:       5,988 sequential scans (0 index scans) ✅
daily_sales:            5 seq scans, 29,578 index scans   ✅
```

materialized views are small. sequential scans are actually faster than indexes for small tables (no index overhead).

### real I/O impact

ran `rails sql:analysis` to get detailed buffer statistics:

**raw user engagement query:**
- 135,233 disk blocks read
- 383,450 cache blocks read
- 1,559 blocks written (temp data)
- 9.26 seconds execution

**materialized view:**
- 0 disk blocks read
- 103 cache blocks read
- 0 blocks written
- 0.0074 seconds execution

the raw query is doing 1300x more I/O. that's why it's slow.

### tools for analysis

added comprehensive SQL analysis tools to the repo:

```bash
# full analysis report
rails sql:analysis

# shows: execution plans, buffer usage, cache hit ratios,
# index usage, query costs, table statistics

# analyze specific query
rails sql:analyze_query QUERY='SELECT * FROM orders WHERE status = "completed"'

# compare raw vs materialized views
rails benchmark:compare
```

the `EXPLAIN ANALYZE` output shows exactly what postgres is doing: parallel workers, sort methods, join types, buffer usage, actual row counts.

check out [PERFORMANCE_ANALYSIS.md](https://github.com/sngeth/scenic-materialized-views-demo/blob/main/PERFORMANCE_ANALYSIS.md) in the repo for the complete breakdown with execution plans and statistics.

## refreshing the views

views get stale. you need to refresh them.

i use a background job with solid queue:

```ruby
class RefreshMaterializedViewsJob < ApplicationJob
  queue_as :default

  def perform
    DailySale.refresh
    TopProduct.refresh
    UserEngagement.refresh
    CategoryRevenue.refresh
  end
end
```

scheduled hourly in production:

```yaml
# config/recurring.yml
production:
  refresh_materialized_views:
    class: RefreshMaterializedViewsJob
    queue: default
    schedule: every hour
```

refreshing all 4 views takes about 27 seconds with my dataset. once an hour is negligible overhead for 350-9000x query speedups.

for larger views or high-traffic sites, use `CONCURRENTLY`:

```ruby
def self.refresh
  Scenic.database.refresh_materialized_view(table_name, concurrently: true)
end
```

requires unique indexes but lets you refresh without locking the view. users can keep querying during refresh.

## when this makes sense

materialized views work when:
- you have complex aggregations that run often
- data staleness of 5-60 minutes is acceptable
- reads massively outnumber writes
- the underlying query is expensive (>500ms)

don't use them for:
- real-time data requirements
- simple queries already fast with indexes
- write-heavy tables that change constantly

my dashboard checks all the boxes. analytics data where hour-old numbers are fine. users hitting the same queries hundreds of times per day.

## the full setup

i open sourced the [complete case study](https://github.com/sngeth/scenic-materialized-views-demo). includes:

- production-ready schema (users, products, orders, activities)
- 4 materialized views with sql
- seed script that generates millions of records
- benchmark rake tasks
- dashboard ui
- automated refresh jobs

you can clone it and run benchmarks yourself:

```bash
git clone https://github.com/sngeth/scenic-materialized-views-demo
cd scenic-materialized-views-demo
bundle install
rails db:create db:migrate
rails db:seed
rails benchmark:refresh
rails benchmark:compare
```

customize data volume with env vars:

```bash
USERS_COUNT=50000 PRODUCTS_COUNT=5000 rails db:seed
```

## some specifics on scenic

scenic handles view versioning like migrations. updating a view:

```bash
rails generate scenic:view daily_sales --version 2
```

creates `daily_sales_v02.sql`. modify the query, run migrations, scenic handles the swap.

you can also drop down to raw sql when needed:

```ruby
ActiveRecord::Base.connection.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY daily_sales")
```

scenic mostly stays out of your way. it's a thin wrapper that makes postgres materialized views feel like rails.

## monitoring refresh performance

track how long refreshes take:

```ruby
def perform
  Rails.logger.info "Starting materialized views refresh..."
  start_time = Time.now

  DailySale.refresh
  Rails.logger.info "  ✓ DailySale refreshed"

  # ... other views

  elapsed_time = Time.now - start_time
  Rails.logger.info "Completed in #{elapsed_time.round(2)}s"
end
```

watch for degradation as data grows. if refreshes start taking too long, consider:
- refreshing views separately with different schedules
- using incremental refresh patterns
- partitioning underlying tables

## practical example: the dashboard controller

here's how simple the controller gets:

```ruby
class DashboardController < ApplicationController
  def index
    @daily_sales = DailySale.order(sale_date: :desc).limit(30)
    @top_products = TopProduct.order(total_revenue: :desc).limit(10)
    @category_revenues = CategoryRevenue.order(total_revenue: :desc)
    @top_users = UserEngagement.order(lifetime_value: :desc).limit(10)
  end
end
```

four simple queries. no joins, no aggregations, no complexity. just reading pre-computed data.

response time? 50-100ms total including rendering. used to be 10+ seconds with raw queries.

the views handle all the heavy lifting in the background refresh job.

## cost analysis

refreshing 4 views takes 27 seconds every hour = 648 seconds per day.

without materialized views, if the dashboard gets hit 1000 times per day (conservative):
- 1000 requests × 4 queries × 3 seconds average = 12,000 seconds of query time
- plus database load, connection pool pressure, etc.

the math checks out. background refresh overhead is tiny compared to saved query time.

## edge cases

**partial data during refresh**: use `CONCURRENTLY` to avoid downtime, but it requires unique indexes and takes longer.

**view dependencies**: if views reference other views, refresh order matters. scenic handles this with cascade options.

**schema changes**: changing underlying tables requires updating and versioning the views. scenic makes this manageable with version files.

**storage**: materialized views duplicate data. monitor disk usage. my 4 views add maybe 50mb on top of 2gb of base tables. negligible.

## wrapping up

350x to 9000x faster queries. 27 seconds of refresh time per hour. hour-old data that's perfectly acceptable for analytics.

materialized views aren't magic. they're cached query results. but for dashboards on millions of rows, they transform unusable into instant.

the scenic gem makes them feel native to rails. write sql, run migrations, query like models.

check out the [full repo](https://github.com/sngeth/scenic-materialized-views-demo) if you want to try it. includes all the benchmarks, views, and a working dashboard you can load with test data.
