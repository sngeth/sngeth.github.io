---
layout: post
title: "Point-free programming"
category: "Functional Programming"
comments: true
---
---
Point-free style, also known as **tacit programming**, is a method of writing functions without explicitly mentioning their arguments. Instead of focusing on **what** the arguments are, point-free style emphasizes **how** functions are combined. This style is prominent in functional programming and can be found in many functional languages, such as Haskell and Elixir.

In this blog post, we'll explore the origins of point-free style, how it's implemented in Haskell and Elixir, and how these two languages compare when it comes to this technique.

## The Origins of Point-Free Style

The roots of point-free style go back to **combinatory logic**, a branch of mathematical logic developed by **Moses Schönfinkel** in the 1920s and later extended by **Haskell Curry**. Combinatory logic aimed to eliminate the need for variables in functions by focusing solely on function composition. This allowed expressions to be more concise and abstract.

The goal of combinatory logic was to describe computations purely through function application and composition without referring to the individual arguments, hence "point-free" (where "points" refer to arguments).

While combinatory logic originated in mathematics, its ideas have strongly influenced functional programming languages. **APL**, developed in the 1960s, was one of the first languages to use a similar concept, and **Miranda**, developed in the 1980s, popularized it further. Haskell, born in the 1990s, adopted and refined this approach, making point-free style a hallmark of functional programming.

## Point-Free Style in Haskell

Haskell is known for its elegant use of function composition and point-free style. In Haskell, you can define functions by composing other functions, without mentioning the arguments.

Here’s a simple example of a point-free function in Haskell:

```haskell
makeGreeting = (<>) . (<> " ")
```

In this case:
- The function `(<>)` is the string concatenation operator.
- The expression `(<>) . (<> " ")` creates a new function that concatenates a space between two strings.

When you call `makeGreeting "hello" "world"`, it returns `"hello world"`. The magic of point-free style here is that you never explicitly mention the arguments `name1` or `name2` — everything is done through function composition.

### Benefits in Haskell

- **Conciseness**: Point-free style reduces the verbosity by removing explicit references to arguments.
- **Readability (in some cases)**: For those accustomed to functional programming, this style can make code more expressive and elegant by highlighting the transformations applied to the data rather than focusing on the data itself.

However, point-free style can become unreadable if overused, especially when the composition involves many functions. This is where balance is key.

## Point-Free Style in Elixir

Elixir, while also a functional programming language, has a slightly different syntax and approach to anonymous functions compared to Haskell. Elixir doesn’t support point-free style as directly as Haskell, but it still allows for a concise definition of anonymous functions using the **capture operator (`&`)**.

Here’s the equivalent of the Haskell point-free example in Elixir:

```elixir
make_greeting = &(&1 <> " " <> &2)
```

In this Elixir version:
- The `&` symbol is a shorthand for anonymous functions.
- `&1` and `&2` refer to the first and second arguments, respectively.

This function behaves the same as its Haskell counterpart: calling `make_greeting.("hello", "world")` will return `"hello world"`.

### Differences in Elixir

Unlike Haskell, Elixir does not emphasize point-free style as much, mainly due to its roots in the **Erlang VM** (which was not designed with pure functional programming in mind). However, Elixir provides the `&` capture operator for defining short, anonymous functions in a concise way, which offers some point-free-like benefits.

#### Example: Haskell vs Elixir

Let’s compare a slightly more complex example in both languages: a function that doubles each element in a list.

- **Haskell**:
  ```haskell
  doubleAll = map (* 2)
  ```
  In Haskell, `doubleAll` is a point-free function that uses `map` to apply `(* 2)` to each element in a list. The function is defined entirely without mentioning the list argument.

- **Elixir**:
  ```elixir
  double_all = &Enum.map(&1, &(&1 * 2))
  ```
  In Elixir, while you can write it concisely using the capture operator (`&`), it’s not as purely point-free as Haskell. Here, you still need to refer to `&1` to indicate the argument, and you call the `Enum.map/2` function.

## Pros and Cons of Point-Free Style

### Advantages
- **Conciseness**: Point-free style leads to more compact code, which can be beneficial when dealing with simple function compositions.
- **Abstraction**: By focusing on composition rather than individual arguments, the code often becomes more abstract and modular.
- **Readability (for small compositions)**: When used correctly, point-free style can make code more expressive by focusing on the logic of function composition.

### Disadvantages
- **Readability (for complex compositions)**: As compositions grow in complexity, point-free style can become difficult to follow, making code harder to understand and maintain.
- **Debugging**: When errors occur, it can be harder to track down the source, as the explicit argument handling is missing.

## Conclusion

Point-free style has its origins in combinatory logic and has found a home in functional programming, particularly in languages like Haskell. Haskell makes point-free style a natural part of its programming model, allowing for elegant function compositions without mentioning arguments.

In contrast, while Elixir supports concise anonymous functions using the capture operator (`&`), it doesn’t fully embrace point-free style in the same way as Haskell. However, both languages allow for powerful functional programming techniques, and knowing when to use or avoid point-free style can lead to clearer, more maintainable code.

The key takeaway is that point-free style is a useful tool, but like any tool, it should be used judiciously, especially as the complexity of your code grows.

---

### References
- Haskell Documentation: [Haskell Function Composition](https://wiki.haskell.org/Function_composition)
- Elixir Documentation: [Elixir Anonymous Functions](https://elixir-lang.org/getting-started/modules-and-functions.html#anonymous-functions)

---

I hope this gives you a good overview of point-free style and how it compares between Haskell and Elixir.
