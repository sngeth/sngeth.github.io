---
layout: post
title: "Locality of Behavior vs SOLID: Finding Balance in Code Organization"
category: "Design Patterns"
comments: true
---

Software companies often push for modular, highly-abstracted code in pursuit of flexibility and maintainability.
However, this approach can inadvertently create significant cognitive overhead for developers, especially those new to a codebase.
As codebases grow more complex and distributed, developers increasingly face mental fatigue from juggling numerous abstractions and navigating sprawling file structures.
This raises an important question: Are our current practices truly serving us, or are they contributing to developer burnout?
The resurgence of interest in locality of behavior, along with the popularity of tools like HTMX and the emergence of "anti-design patterns,"
suggests a growing desire for simpler, more cognitively manageable code structures. But how do we balance these competing concerns?

Reflecting on my experience applying for a software internship in 2008, I recall being bombarded with questions about object-oriented programming (OOP), inheritance, and polymorphism.
At the time, these concepts were considered essential for writing and understanding modular code.
The industry's focus on these principles stemmed from the belief that they led to more maintainable and scalable software.
However, this approach raises an important question: Did the emphasis on OOP truly prepare developers for the complexities of real-world software development?
While these concepts can be powerful tools, they don't necessarily justify the cognitive overhead they introduce.
Interview questions rarely addressed the critical skill of determining when such complexity is warranted or how to balance modularity with code readability and maintainability. This disconnect between interview practices and practical development needs highlights the ongoing challenge of finding the right balance in code organization and design.

## Understanding Locality of Behavior

Before diving into code organization patterns, let's understand a fundamental principle that often conflicts with traditional SOLID advice: Locality of Behavior (LoB).

Locality of Behavior was prominently discussed by Richard P. Gabriel in his patterns work and gained more attention through Alan Kay's ideas about object-oriented programming. However, it really entered mainstream discussion through Rich Hickey (creator of Clojure) who has spoken about it extensively.

The core idea is simple but powerful: **code should be organized so that related behaviors are kept close together**. In other words, all the code needed to understand a particular operation should be in the same place.

This principle has strong academic roots:
1. Richard P. Gabriel discussed it in "Patterns of Software: Tales from the Software Community" (1996)
2. Rich Hickey's "Simple Made Easy" presentation explores the cognitive overhead of scattered code
3. John Ousterhout's "A Philosophy of Software Design" (2018) discusses "deep modules" that keep implementation details close to their interface

Let's examine how this principle plays out in real code.

## The Case for Keeping Things Together

First, let's look at code with high locality of behavior:

```ruby
class FileProcessor
  def process(file)
    case file.extension
    when '.csv'
      process_csv(file)    # CSV behavior is local
    when '.json'
      process_json(file)   # JSON behavior is local
    end
  end

  private

  def process_csv(file)
    CSV.read(file.path).map { |row| row.map(&:strip) }  # The full CSV behavior is visible right here
  end

  def process_json(file)
    JSON.parse(File.read(file.path))                    # The full JSON behavior is visible right here
  end
end
```

Compare this with code that has low locality of behavior:

```ruby
class FileProcessor
  def process(file)
    processor_for(file.extension).process(file)  # Have to look elsewhere to find the processor
  end
end

class CsvProcessor
  def process(file)
    clean_values(           # Have to look elsewhere to find what clean_values does
      read_csv(file)       # Have to look elsewhere to find what read_csv does
    )
  end
end

module ValueCleaner
  def clean_values(data)   # The actual behavior is far from where it's used
    data.map { |row| row.map(&:strip) }
  end
end
```

## The Great SOLID Debate

Before we dive deeper, let's address the elephant in the room: SOLID principles, particularly the Open/Closed Principle (OCP), have faced criticism in recent years. Critics argue that breaking everything into separate files and abstractions can actually make code harder to understand. They have a point – let's look at both sides.

## Different Approaches to Code Organization

### The Inheritance Approach

Here's how many developers first attempt to separate concerns:

```ruby
# base_processor.rb
class BaseProcessor
  def process(file)
    raise NotImplementedError
  end

  protected

  def strip_values(data)
    data.map { |row| row.map(&:strip) }
  end
end

# csv_processor.rb
class CsvProcessor < BaseProcessor
  def process(file)
    data = CSV.read(file.path)
    strip_values(data)
  end
end

# json_processor.rb
class JsonProcessor < BaseProcessor
  def process(file)
    JSON.parse(File.read(file.path))
  end
end

# file_processor.rb
class FileProcessor
  PROCESSORS = {
    '.csv' => CsvProcessor,
    '.json' => JsonProcessor
  }

  def process(file)
    processor_class = PROCESSORS[file.extension] ||
      raise("Unsupported format: #{file.extension}")

    processor_class.new.process(file)
  end
end
```

**Mental Model Required:**
- Understand class inheritance
- Know to look in multiple files
- Grasp abstract base classes
- Learn about class registration patterns

**New Developer Questions:**
> "Why do we need a BaseProcessor? Where are the actual processing methods? How do I find which processor handles which format? Why is strip_values in the base class?"

### The Composition Approach

Here's a composition-based approach:

```ruby
# processors/csv.rb
module Processors
  class Csv
    def self.process(file)
      new(file).process
    end

    def initialize(file)
      @file = file
    end

    def process
      ValueCleaner.new(
        CsvReader.new(@file)
      ).process
    end
  end
end

# processors/components/csv_reader.rb
class CsvReader
  def initialize(file)
    @file = file
  end

  def process
    CSV.read(@file.path)
  end
end

# processors/components/value_cleaner.rb
class ValueCleaner
  def initialize(source)
    @source = source
  end

  def process
    @source.process.map { |row| row.map(&:strip) }
  end
end

# file_processor.rb
class FileProcessor
  PROCESSORS = {
    '.csv' => Processors::Csv,
    '.json' => Processors::Json
  }

  def process(file)
    processor_class = PROCESSORS[file.extension] ||
      raise("Unsupported format: #{file.extension}")

    processor_class.process(file)
  end
end
```

**Mental Model Required:**
- Understand object composition
- Grasp dependency injection
- Know about component assembly
- Navigate deeper directory structures

**New Developer Questions:**
> "Why are there so many small classes? How do these pieces fit together? Where does the processing actually happen? How do I trace the flow?"

## Finding Balance: A More Approachable Solution

Here's a middle ground that maintains separation while being more approachable:

```ruby
# file_processor.rb
class FileProcessor
  def process(file)
    processor_for(file.extension).process(file)
  end

  private

  def processor_for(extension)
    case extension
    when '.csv' then CsvProcessor.new
    when '.json' then JsonProcessor.new
    else raise "Unsupported format: #{extension}"
    end
  end
end

# processors.rb
class CsvProcessor
  def process(file)
    clean_values(
      read_csv(file)
    )
  end

  private

  def read_csv(file)
    CSV.read(file.path)
  end

  def clean_values(data)
    data.map { |row| row.map(&:strip) }
  end
end

class JsonProcessor
  def process(file)
    JSON.parse(File.read(file.path))
  end
end
```

**Mental Model Required:**
- Basic object-oriented programming
- Simple method delegation
- Two files to navigate

**New Developer Experience:**
> "I can see how processors are selected and where their logic lives. Adding a new format means adding a new processor class with a process method. The processing steps are clear within each processor."

## Key Insights for Real-World Development

1. **Cognitive Load Matters**
   - Every layer of abstraction is a concept developers must hold in their head
   - More files = more context switching
   - Simpler patterns = faster onboarding

2. **The Cost of Flexibility**
   - Inheritance creates rigid hierarchies that are hard to change
   - Deep composition can make code flow hard to follow
   - Not every difference needs its own abstraction

3. **Signs You Might Be Over-Separating**
   - You need a diagram to explain the code structure
   - New developers frequently ask "where does X happen?"
   - Changes require touching many files
   - Test setup becomes complex

4. **When Separation Makes Sense**
   - Processing logic is complex (>20-30 lines)
   - Components have different deployment/testing needs
   - Different teams own different processors
   - Performance requires lazy loading

## Practical Guidelines

1. **Start Together**
   - Keep code in one place until patterns emerge
   - Don't separate based on speculation
   - Let real requirements drive design

2. **Separate Gradually**
   - Move code out when it proves necessary
   - Keep related code close together
   - Document why separation was needed

3. **Optimize for Understanding**
   - Could a new developer understand this in their first week?
   - Is the separation making the code clearer or just more "proper"?
   - Are you solving real problems or theoretical ones?

## Benefits of Locality of Behavior

1. Reduced cognitive load - developers don't have to jump between files
2. Easier debugging - the full context is visible
3. Better performance - related code tends to be loaded together
4. Simpler testing - fewer dependencies to mock

The principle doesn't mean "put everything in one file" but rather "keep related behaviors together." The challenge is determining what "related" means in your specific context.

## Conclusion

The best code isn't the most perfectly separated – it's the code that helps your team move quickly and confidently. Sometimes that means keeping things together, even if it doesn't satisfy every SOLID principle.

Remember: Every layer of indirection you add is a concept that must live in a developer's mental model of the system. Choose wisely.

What's your experience with code organization patterns? How do you balance separation with understandability? Share your thoughts in the comments below.

## References

1. Gabriel, Richard P. (1996). "Patterns of Software: Tales from the Software Community"
2. Hickey, Rich. "Simple Made Easy" presentation
3. Ousterhout, John. (2018). "A Philosophy of Software Design"
