---
layout: post
title:  "Closures in Javascript"
category: "Javascript"
comments: true
---
## What is a closure?

A closure is when a function "remembers" its lexical scope even when
the function is executed outside that lexical scope.

```javascript
function makeAdder(x) {
  return function(y) {
    return x + y;
  };
}

var add5 = makeAdder(5);
var add10 = makeAdder(10);

console.log(add5(2));  // 7
console.log(add10(2)); // 12
```

```add5``` and ```add10``` have both become closures because they share the same function body definition but
store different environments and close over the x and y independently.
The key mechanism at work here is the inner function is be transported
out and returned.

## Module pattern
A useful application of closures is the module pattern which can provide
a means of encapsulation.

```javascript
var foo = (function() {
  var o = { bar: "bar" };

  return {
    bar: function() {
      console.log(o.bar);
    }
  };
})();

foo.bar(); // "bar"
foo.o // "undefined" - akin to a private member
```

