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
