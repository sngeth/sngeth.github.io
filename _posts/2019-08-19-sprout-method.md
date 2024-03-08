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
  // TDD this new method
  List uniqueEntries(List entries) {
    //remove duplicate entries
  }

  public void postEntries(List entries) {
    List entriesToAdd = uniqueEntries(entries);
    // iterate through entries list and persist the transaction
  }
}
```

### Addendum (3/7/2024):

In response to feedback and to provide further clarity, I'd like to emphasize the importance of understanding the "sprout method" concept and its application in software development.

**Understanding the "Sprout Method" Concept:**

The "sprout method" pattern involves extracting a new method from existing code to encapsulate specific functionality. This approach promotes code modularity, readability, and maintainability by adhering to the Single Responsibility Principle (SRP). By isolating distinct tasks into separate methods, developers can create more cohesive and reusable code.

**Benefits of Using the "Sprout Method" Pattern:**

1. **Improved Code Organization:** The "sprout method" pattern allows developers to organize code more effectively by grouping related functionality into separate methods. This enhances code readability and makes it easier to understand the purpose and behavior of each method.

2. **Enhanced Testability:** Extracting logic into separate methods facilitates unit testing, as it isolates specific behaviors for testing. With focused, well-defined methods, developers can write more targeted tests with clear inputs and expected outputs.

3. **Easier Maintenance and Refactoring:** By adhering to the SRP and separating concerns, the "sprout method" pattern simplifies maintenance and refactoring efforts. Developers can modify or extend individual methods without impacting other parts of the codebase, reducing the risk of unintended side effects.

**Applying the "Sprout Method" Pattern in Practice:**

When faced with the task of adding new functionality or modifying existing code, consider whether the "sprout method" pattern can help improve code structure and maintainability. Look for opportunities to extract cohesive, reusable methods that encapsulate specific behaviors or operations.

In summary, understanding and applying the "sprout method" pattern can lead to cleaner, more maintainable codebases. By leveraging this pattern effectively, developers can enhance code organization, testability, and overall software quality.
