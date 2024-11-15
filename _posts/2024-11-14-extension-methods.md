---
layout: post
title: "The Surprising Connection Between Smalltalk, Ruby, and C#: A Tale of Extension Methods"
category: "Programming Languages"
comments: true
---
When developers think of C#'s extension methods, they often associate them with LINQ and .NET's modern features. But did you know that this powerful programming concept has roots dating back to the 1970s?

![Smalltalk](/public/images/smalltalk.png){: .img-fluid .mx-auto .d-block style="max-width: 100%; height: auto;"}

## The Smalltalk Origins

In the 1970s, Smalltalk introduced a revolutionary concept called "open classes." This feature allowed developers to add methods to existing classes, even core library classes, at runtime. Here's what it looked like:

```smalltalk
Object subclass: #String
    instanceMethods: [
        shout [
            ^self asUppercase, '!'
        ]
    ]
```

This was groundbreaking at the time - the ability to modify existing types without subclassing them. This feature would later influence many modern programming languages.

## Ruby's "Monkey Patching"

Fast forward to the 1990s, and Ruby embraced this concept with its own implementation of open classes:

```ruby
class String
  def shout
    self.upcase + "!"
  end
end

# Now every String instance has access to this method
puts "hello".shout  # Outputs: HELLO!
```

This feature became so popular (and sometimes notorious) in Ruby that it earned the nickname "monkey patching." While powerful, it highlighted both the benefits and potential dangers of unrestricted type extension.

## C#: Formalizing the Concept

In 2007, C# 3.0 introduced what we now know as "extension methods." This implementation took the lessons learned from dynamic languages and added static typing safety:

```csharp
public static class StringExtensions
{
    public static string Shout(this string str)
    {
        return str.ToUpper() + "!";
    }
}

// Usage
"hello".Shout();  // Returns: "HELLO!"
```

C# formalized the concept and coined the term "extension methods" that many modern languages now use. The implementation addressed several key challenges:

1. **Safety**: Extensions can't override existing methods
2. **Scope**: Extensions must be explicitly imported
3. **Clarity**: The syntax makes it clear that it's an extension
4. **Performance**: Compile-time binding for better efficiency

## Modern Language Implementations

### CLOS (Common Lisp Object System)
```lisp
;; Using generic functions
(defgeneric shout (thing))

(defmethod shout ((text string))
  (concatenate 'string (string-upcase text) "!"))

;; Usage
(shout "hello") ; Returns "HELLO!"
```

### Kotlin
```kotlin
// Extension function
fun String.shout() = this.uppercase() + "!"

// Extension property
val String.doubleLength: Int
    get() = this.length * 2

// Extension with generics
fun <T> List<T>.secondOrNull(): T? = if (this.size >= 2) this[1] else null

// Usage
println("hello".shout())          // HELLO!
println("test".doubleLength)      // 8
listOf(1,2,3).secondOrNull()      // returns 2
```

### Swift
```swift
extension String {
    // Simple extension
    func shout() -> String {
        return self.uppercased() + "!"
    }

    // Computed property
    var doubleLength: Int {
        return self.count * 2
    }

    // With parameters
    func repeated(times: Int) -> String {
        return String(repeating: self, count: times)
    }
}

// Usage
"hello".shout()           // "HELLO!"
"test".doubleLength       // 8
"ha".repeated(times: 3)   // "hahaha"
```

### Scala
```scala
object StringExtensions {
    implicit class StringOps(val s: String) {
        def shout: String = s.toUpperCase + "!"

        def reverseShout: String = s.reverse.toUpperCase + "!"

        // With parameters
        def repeatTimes(n: Int): String = s * n
    }
}

// Usage
import StringExtensions._
"hello".shout        // "HELLO!"
"hello".reverseShout // "OLLEH!"
"ha".repeatTimes(3)  // "hahaha"
```

### TypeScript
```typescript
declare global {
    interface String {
        shout(): string;
        reverseShout(): string;
    }
}

String.prototype.shout = function(): string {
    return this.toUpperCase() + "!";
};

String.prototype.reverseShout = function(): string {
    return this.split('').reverse().join('').toUpperCase() + "!";
};

// Usage
"hello".shout();        // "HELLO!"
"hello".reverseShout(); // "OLLEH!"
```

### Rust (Using Traits)
```rust
trait StringExtension {
    fn shout(&self) -> String;
    fn reverse_shout(&self) -> String;
}

impl StringExtension for String {
    fn shout(&self) -> String {
        format!("{}!", self.to_uppercase())
    }

    fn reverse_shout(&self) -> String {
        format!("{}!", self.chars().rev()
            .collect::<String>().to_uppercase())
    }
}

// Usage
let text = String::from("hello");
println!("{}", text.shout());         // "HELLO!"
println!("{}", text.reverse_shout()); // "OLLEH!"
```

## What Makes This Interesting?

The evolution of extension methods shows how programming languages learn from each other:

1. **Smalltalk** proved the concept was useful
2. **Ruby** showed both the power and potential pitfalls
3. **C#** formalized the approach with static typing
4. **Modern languages** refined the implementation further

## Key Takeaways

1. Many modern programming features have roots in older languages
2. Different languages can learn from each other across paradigms
3. Good ideas evolve as we learn their strengths and weaknesses
4. Static and dynamic languages can inspire each other's features
