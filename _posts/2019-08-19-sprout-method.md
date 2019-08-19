---
layout: post
title:  "Sprout Method"
comments: true
---
Write tests for new code even if the old code isn't under test. Although
this isn't a good long term solution it can help move the design
forward.

For simple changes that can be captured in a method we can TDD that.

Let's say we have some existing code:

```java
public class TransactionGate
{
  public void postEntries(List entries) {
    // iterate through entries list and persist the transaction
  }
}
```

Now we want to remove duplicate entry's before persisting them. A quick
thing to do is write the new logic directly inside postEntries but this
is bad for several reasons such as SRP violation. Instead we can sprout
a new method called uniqueEntries and call it inside postEntries

```java

public class TransactionGate
{
  List uniqueEntries(List entries) {
    //remove duplicate entries
  }

  public void postEntries(List entries) {
    List entriesToAdd = uniqueEntries(entries);
    // iterate through entries list and persist the transaction
  }
}
```
