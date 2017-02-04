---
layout: post
title:  "Functional Programming in Ruby"
comments: true
---
Although I've been focusing learning functional programming through Elixir
and Elm these days, it's interesting to go back to the first programming
language I love to see what it can do.

These are some examples of Ruby's functional programming abilities taken from
HackerRank's Ruby challenges.

Ruby can support higher-order functions i.e. can take and pass functions as
arguments through several mechanisms: Blocks, Procs, and Lambdas. I'm not going
to go into super detail as there are plenty
[good posts](http://awaxman11.github.io/blog/2013/08/05/what-is-the-difference-between-a-block/)
already out there on the topic. But a basic primer goes as follows:

Passing a Block to a function as nameless method:

```ruby
def calculate(a,b)
    yield(a, b)
end

puts calculate(15, 10) {|a, b| a - b} # 5
```

Assigning a Proc to a variable. Proc's are like a "saved" block:

```ruby
def foo(a, b, my_proc)
    my_proc.call(a, b)
end

add = proc {|x, y| x + y}

puts foo(15, 10, add) # 25
```

Very similar to Procs but differing how they return (see link mentioned beginning
of post) out of a function call is Ruby's lambda.

```ruby
# the -> keyword is Ruby >= 1.9's lambda syntax
area = ->(a, b) { a * b }

x = 10.0; y = 20.0

area_rectangle = area.(x, y)
area_triangle = 0.5 * area.call(x, y)

puts area_rectangle     #200.0
puts area_triangle      #100.0   
```

Let's dig into an interesting example where we show partial function applications

```ruby
def factorial(n)
    (1..n).inject(:*) || 1
end


combination = -> (n) do
    -> (r) do
        factorial(n) / (factorial(r) * factorial(n-r))
    end
end

#How many combinations in 52 card deck when taking 5 cards?
n = gets.to_i # Let's enter 52
r = gets.to_i # Let's enter 5
nCr = combination.(n) # returns a lambda object
puts nCr.(r) # call our lambda with 2nd argument to be applied, result is 2,598,960

```

So similar to partial function applications is the concept of currying.
Currying is converting a single function of n arguments into n functions with a
single argument each.

```ruby
power_function = -> (x, z) {
    (x) ** z
}

base = gets.to_i
raise_to_power = power_function.curry.(base)

power = gets.to_i
puts raise_to_power.(power)
```
