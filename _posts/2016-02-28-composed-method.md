---
layout: post
title:  "Composed Method"
category: "Design Patterns"
comments: true
---
Definition: Breaking down a method into smaller intention revealing methods

Example:

```ruby
def controlActivity
  controlInitialize
  controlLoop
  controlTerminate
end
```

The above code is very readable and communicates at the same abstraction level.
We are guiding the structure of the system subtly by the naming and chunking.

In fact we can design our system top down and leave the implementation details
for later.

A pleasant side effect of intention revealing methods within this composed
method is that we hide the implementation details of methods
making it more extensible and easier to modify. E.g.:

```ruby
# original implementation
def controlInitialize(args)
  activity_name = args[:activity_name]
end

# adding a description
def controlInitialize(args)
  activity_name = args[:activity_name]
  description = args[:description]
end
```

We can also actually use Composed Method bottom-up to DRY up our code. I.e
```controlInitialize``` can now be called in multiple places and changed in one
place.

If the above method was an overridable method in a superclass, we now only have 1
method we need to override vs large chunks of random code in the superclass.
