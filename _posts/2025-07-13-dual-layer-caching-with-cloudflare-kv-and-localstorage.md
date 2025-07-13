---
layout: post
title: "dual-layer caching with cloudflare kv and localstorage"
categories: cloudflare javascript
---

built a movie recommendation app that uses ai to analyze content themes. the challenge? each openai api call costs money and takes time. the solution? a dual-layer caching strategy that maximizes performance while minimizing costs.

## the problem

calling openai's api for every movie analysis is expensive and slow:
- **cost**: $0.002 per 1k tokens with gpt-4o-mini
- **latency**: 500-2000ms per request
- **scale**: same movies analyzed repeatedly by different users

simple client-side caching helps individual users, but doesn't solve the broader cost problem when multiple users analyze the same popular movies.

## dual-layer approach

implemented two complementary caching layers:

### layer 1: localstorage (client-side)
```javascript
function getCachedAnalysis(movieTitle, year) {
  const cache = JSON.parse(localStorage.getItem('movieAnalysisCache') || '{}');
  const key = `${movieTitle}_${year}`;
  const cached = cache[key];
  
  if (cached && cached.timestamp) {
    const ageInDays = (Date.now() - cached.timestamp) / (1000 * 60 * 60 * 24);
    if (ageInDays < 30) {
      return cached.analysis;
    }
  }
  return null;
}
```

### layer 2: cloudflare kv (server-side)
```javascript
export async function onRequest(context) {
  const { request, env } = context;
  const { title, synopsis, year } = await request.json();
  
  const cacheKey = `analysis:${title}_${year}`.replace(/[^a-zA-Z0-9_-]/g, '_');
  
  // check kv cache first
  const cached = await env.KV.get(cacheKey, { type: 'json' });
  if (cached) {
    return new Response(JSON.stringify(cached), {
      headers: { 'X-Cache': 'HIT' }
    });
  }
  
  // cache miss - call openai
  const analysis = await callOpenAI(title, synopsis, year);
  
  // store in kv for 30 days
  await env.KV.put(cacheKey, JSON.stringify(analysis), {
    expirationTtl: 2592000
  });
  
  return new Response(JSON.stringify(analysis), {
    headers: { 'X-Cache': 'MISS' }
  });
}
```

## how they work together

the caching cascade works like this:

1. **client checks localstorage** - if hit, no network request needed
2. **if miss, calls api** - server function gets invoked
3. **server checks kv cache** - if hit, returns cached result (no openai cost)
4. **if miss, calls openai** - makes expensive api call
5. **server stores in kv** - future users benefit from cache
6. **client stores in localstorage** - future requests from same user skip network

```javascript
// client-side flow
const cachedAnalysis = getCachedAnalysis(movie.title, movie.year);
if (cachedAnalysis) {
  // best case: instant local cache hit
  displayAnalysis(cachedAnalysis);
  return;
}

// cache miss - make api call
const response = await fetch('/api/analyze-content', {
  method: 'POST',
  body: JSON.stringify({ title: movie.title, synopsis: movie.synopsis, year: movie.year })
});

const analysis = await response.json();
setCachedAnalysis(movie.title, movie.year, analysis); // store locally
displayAnalysis(analysis);
```

## performance characteristics

this creates three distinct performance scenarios:

| scenario | network | openai cost | latency |
|----------|---------|-------------|---------|
| localstorage hit | none | $0 | ~1ms |
| kv hit | api call | $0 | ~100ms |
| cache miss | api call | ~$0.01 | ~1500ms |

## cost analysis

for a popular movie analyzed by 1000 users:
- **without caching**: 1000 × $0.01 = $10.00
- **with localstorage only**: 1000 × $0.01 = $10.00 (no sharing)
- **with dual-layer**: 1 × $0.01 = $0.01 (99.9% savings)

the kv cache effectively amortizes the openai cost across all users.

## cloudflare kv setup

cloudflare pages automatically injects kv bindings into function context through the dashboard:

1. create kv namespace in cloudflare dashboard
2. bind it to your pages project via dashboard ui (variable name: `KV`)
3. the binding appears as `env.KV` in your functions automatically

no configuration files needed - it's all done through the cloudflare dashboard interface.

## cache invalidation

both layers use 30-day expiration:
- **localstorage**: timestamp-based expiration check
- **kv**: cloudflare's native ttl handling

```javascript
// localstorage expiration
const ageInDays = (Date.now() - cached.timestamp) / (1000 * 60 * 60 * 24);
if (ageInDays < 30) {
  return cached.analysis;
}

// kv expiration (automatic)
await env.KV.put(cacheKey, data, {
  expirationTtl: 2592000 // 30 days in seconds
});
```

## debugging cache behavior

added cache status headers to track hit/miss patterns:

```javascript
return new Response(JSON.stringify(analysis), {
  headers: {
    'Content-Type': 'application/json',
    'X-Cache': cached ? 'HIT' : 'MISS'
  }
});
```

can monitor in browser devtools to verify caching is working.

## alternatives considered

**redis**: would work but adds infrastructure complexity
**cdn caching**: doesn't work for dynamic post requests
**database caching**: overkill for simple key-value needs
**memory caching**: doesn't persist across deployments

cloudflare kv hits the sweet spot - globally distributed, zero infrastructure, tight pages integration.

## trade-offs

**pros**:
- massive cost reduction for popular content
- improved user experience (faster responses)
- zero infrastructure management
- global edge caching

**cons**:
- slightly more complex than single-layer
- potential for stale data (30-day window)
- kv has eventual consistency (rare edge case)

## implementation tips

1. **cache key normalization** - strip special characters to avoid kv key issues
2. **graceful degradation** - if kv fails, still call openai
3. **cache warming** - consider pre-caching popular movies
4. **monitoring** - track hit rates and costs

## conclusion

dual-layer caching with localstorage and cloudflare kv provides the best of both worlds - instant local performance and shared cost benefits. for api-heavy applications, this pattern can dramatically reduce costs while improving user experience.

the key insight is that not all caching needs to be shared - combining individual and collective caching layers creates optimal performance characteristics for different use cases.