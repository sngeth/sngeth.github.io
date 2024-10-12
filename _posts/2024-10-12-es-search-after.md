---
layout: post
title: "Using search_after with Elasticsearch-Rails: Efficient Pagination for Large Datasets"
category: "Elasticsearch"
comments: true
---

When working with large datasets in Elasticsearch, efficient pagination becomes crucial for maintaining performance. The `search_after` parameter offers a solution by allowing you to paginate through results based on the sorting values of the last document from the previous page. In this post, we'll explore how to implement `search_after` pagination using the Elasticsearch-Rails gem.

## Why Use `search_after`?

Traditional pagination using `from` and `size` parameters can become inefficient for deep pages, as Elasticsearch needs to calculate and skip over a large number of documents. `search_after` provides a more scalable approach by using the sort values of the last seen document as a search marker.

## Implementation Steps

### 1. Set Up Your Model

First, ensure your model is set up with Elasticsearch:

```ruby
class Product < ApplicationRecord
  include Elasticsearch::Model
  include Elasticsearch::Model::Callbacks

  # Define your index settings and mappings here
end
```

### 2. Define a Custom Search Method

Create a class method in your model to handle the `search_after` logic:

```ruby
class Product < ApplicationRecord
  # ...

  def self.search_with_after(query, sort_field, search_after = nil, size = 20)
    search_definition = {
      query: query,
      sort: [
        { sort_field => { order: 'asc' } },
        { id: { order: 'asc' } }  # Tie-breaker
      ],
      size: size
    }

    search_definition[:search_after] = search_after if search_after

    __elasticsearch__.search(search_definition)
  end
end
```

### 3. Perform the Initial Search

In your controller or service object, perform the initial search:

```ruby
query = { match: { name: 'example' } }
results = Product.search_with_after(query, :created_at)

@products = results.records
@last_sort_values = results.records.last&.slice(:created_at, :id)&.values
```

### 4. Implement Pagination in Your View

In your view, add a "Next Page" link that includes the last sort values:

```erb
<% @products.each do |product| %>
  <!-- Display product information -->
<% end %>

<% if @last_sort_values %>
  <%= link_to "Next Page", products_path(search_after: @last_sort_values.to_json) %>
<% end %>
```

### 5. Handle Subsequent Searches

In your controller, handle the `search_after` parameter for subsequent pages:

```ruby
class ProductsController < ApplicationController
  def index
    query = { match: { name: params[:q] } }
    search_after = JSON.parse(params[:search_after]) if params[:search_after]

    results = Product.search_with_after(query, :created_at, search_after)

    @products = results.records
    @last_sort_values = results.records.last&.slice(:created_at, :id)&.values
  end
end
```

## Considerations and Best Practices

1. **Consistent Sorting**: Ensure your sort fields are consistent across searches to maintain proper pagination.
2. **Tie-breakers**: Always include a tie-breaker field (like `id`) in your sort to handle documents with identical sort values.
3. **Statelessness**: `search_after` is stateless, making it suitable for scenarios where users might open multiple browser tabs or share links.
4. **Performance**: While more efficient than deep offset pagination, be mindful of very large result sets and consider implementing reasonable limits.
