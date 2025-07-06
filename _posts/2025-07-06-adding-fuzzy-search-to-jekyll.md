---
layout: post
title: "adding fuzzy search to a jekyll blog"
categories: jekyll javascript
---

wanted to add search to my blog without any server-side complexity or external services. turns out jekyll's liquid templating makes this surprisingly elegant.

## the liquid magic

jekyll can generate json files during build time. here's the key insight - we can loop through all posts and create a searchable index:

{% raw %}
```liquid
---
layout: null
---
[
  {% for post in site.posts %}
    {
      "title": "{{ post.title | escape }}",
      "excerpt": "{{ post.excerpt | strip_html | truncatewords: 50 | escape }}",
      "url": "{{ post.url }}",
      "date": "{{ post.date | date: '%B %d, %Y' }}",
      "categories": {{ post.categories | jsonify }}
    }{% unless forloop.last %},{% endunless %}
  {% endfor %}
]
```
{% endraw %}

the `layout: null` tells jekyll to output raw json without any html wrapper. the `{% raw %}{% unless forloop.last %}{% endraw %}` handles the trailing comma problem that would break json parsing.

## automatic reindexing

this is the beautiful part - no rake tasks or manual reindexing needed. every time you run `jekyll build` or `jekyll serve`, the search.json gets regenerated with your latest posts. jekyll's build process handles the entire search index automatically.

## fuse.js integration

for the actual search, fuse.js does the heavy lifting. it's 6kb gzipped and handles fuzzy matching really well:

```javascript
fetch('/search.json')
  .then(response => response.json())
  .then(data => {
    fuse = new Fuse(data, {
      keys: ['title', 'excerpt', 'categories'],
      threshold: 0.3,
      includeScore: true
    });
  });
```

the `threshold: 0.3` is the sweet spot - strict enough to avoid nonsense results but loose enough to catch typos and partial matches.

## why this approach works

- **no server required** - everything happens client-side
- **no build complexity** - uses jekyll's existing templating
- **always current** - updates with every build
- **fast** - json loads once, search happens locally
- **lightweight** - fuse.js is tiny, no dependencies

## search ui

added a simple input to the sidebar that shows results as you type:

```javascript
searchInput.addEventListener('input', function(e) {
  const query = e.target.value.trim();

  if (query.length < 2) {
    searchResults.innerHTML = '';
    return;
  }

  const results = fuse.search(query);
  displayResults(results);
});
```

only triggers after 2 characters to avoid noise. shows up to 5 results with title, excerpt, and date.

## liquid templating gotchas

few things to watch out for:

- **json escaping** - use `| jsonify` filter instead of `| escape` for proper json encoding
- **strip html and newlines** - excerpts need `| strip_html | strip_newlines` to avoid json breaks
- **arrays** - jekyll's `| jsonify` filter handles arrays and escaping automatically
- **trailing commas** - the `{% raw %}{% unless forloop.last %}{% endraw %}` pattern prevents json errors

## csp considerations

if you're using content security policy, you'll need to allow the fuse.js cdn and local fetch requests:

```html
script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'
connect-src 'self' https://disqus.com
```

or download fuse.js locally to avoid external dependencies entirely.
