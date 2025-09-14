---
layout: post
title: "how that cloudflare outage happened (and how to avoid it)"
date: 2025-09-14
categories: react debugging
---

so cloudflare had this massive outage recently. their tenant service api went down, taking the dashboard and a bunch of other apis with it. the root cause? a react useEffect dependency array bug that made their dashboard hammer the api with unnecessary requests.

here's what went wrong...

## the setup

they had a react component that needed to fetch data from their tenant service api. pretty standard stuff - throw it in a useEffect, call it a day:

```javascript
useEffect(() => {
  fetchTenantData(config);
}, [config]);
```

looks fine, right? except `config` was an object that got recreated on every render.

## why objects break dependency arrays

react's dependency array uses Object.is() to check if dependencies changed (verified in react's source - see `packages/shared/objectIs.js`). for primitives like strings and numbers, this works great:

```javascript
Object.is('hello', 'hello') // true
Object.is(42, 42) // true
```

but for objects and arrays? different story:

```javascript
Object.is({a: 1}, {a: 1}) // false!
Object.is([1, 2], [1, 2]) // false!
```

even if the contents are identical, they're different object references. so when you do this:

```javascript
function Dashboard() {
  const config = { endpoint: '/api/tenant' }; // new object every render!

  useEffect(() => {
    fetchData(config);
  }, [config]); // this runs every single render
}
```

that effect runs on every render. every state update. every prop change. everything.

## the cascade failure

here's where it gets interesting. the dashboard wasn't just making one extra call - it was making dozens. why? because the api call itself was probably updating state:

1. component renders → creates new config object
2. useEffect sees "new" dependency → calls api
3. api response updates state → triggers re-render
4. go to step 1

add multiple components doing this, users refreshing the page, and a recent service update that made the tenant service less stable... boom. you've got an outage.

## how to fix it

few options here:

### option 1: useMemo

memoize the object so it keeps the same reference:

```javascript
const config = useMemo(() => ({
  endpoint: '/api/tenant'
}), []); // only create once

useEffect(() => {
  fetchData(config);
}, [config]); // now this only runs once
```

### option 2: primitive dependencies

instead of passing the whole object, use primitive values:

```javascript
const endpoint = '/api/tenant';

useEffect(() => {
  fetchData({ endpoint });
}, [endpoint]); // strings compare by value
```

### option 3: move it outside

if the config never changes, define it outside the component:

```javascript
const CONFIG = { endpoint: '/api/tenant' };

function Dashboard() {
  useEffect(() => {
    fetchData(CONFIG);
  }, []); // no dependency needed
}
```

## how eslint might have made it worse

here's the ironic part: the `exhaustive-deps` rule might have actually caused this bug!

```json
{
  "rules": {
    "react-hooks/exhaustive-deps": "error"
  }
}
```

imagine you start with this:

```javascript
function Dashboard() {
  const config = { endpoint: '/api/tenant' };

  useEffect(() => {
    fetchData(config);
  }, []); // eslint error: missing dependency 'config'
}
```

the linter complains that `config` is used but not in the deps array. so you "fix" it:

```javascript
useEffect(() => {
  fetchData(config);
}, [config]); // linter happy, performance dead
```

now your effect runs on every render because `config` is a new object each time. the linter pushed you into the bug!

the real fix is understanding why the warning exists and addressing the root cause (memoizing the object, using primitives, or moving it outside the component) rather than just making the linter happy.
