---
layout: post
title:  "Double Dispatch"
category: "Design Patterns"
comments: true
---
How can you code a computation that has many cases, the cross product of
two families of classes? In a language like Ruby that does
not support method overloading, we would need to rely on a low level
pattern known as double dispatch.

The example below illustrates the dependency on the class of the
object(Doctor or Dentist) and the class of the input object(Adult or Child).
If we don't use double dispatch we get a nasty case of if or switch
statements

```ruby
#Not using double dispatch
class Doctor
  def work_on(patient)
    if patient.is_a? Child
      #patient.do_child_work
    elsif patient.is_a? Adult
      #patient.do_adult_work
      #elseif potential maintenance explosions here
    end
  end
end

class Dentist
  def work_on(patient)
    if patient.is_a? Child
      #patient.do_child_work
    elsif patient.is_a? Adult
      #patient.do_adult_work
      #elseif potential maintenance explosions here
    end
  end
end
```

Using double dispatch below, we can cleanly decouple the type of work to
be done and get rid of type checking

```ruby
#Using double dispatch
class Doctor
  def work_on(patient)
    patient.dispatch_work(self)
  end

  def work_on_adult(patient)
    do_checkup(patient)
  end

  def work_on_child(patient)
    assure_presence_of(patient.guardian)
    ask_questions_to(patient.guardian)
    do_checkup(patient)
    give_cheap_toy_to(patient)
  end

  private
  def do_checkup(patient)
    puts "Checking all your adult aparts"
  end
end

class Dentist
  def work_on(patient)
    patient.dispatch_work(self)
  end

  def work_on_adult(patient)
    drill_as_hard_as_you_can(patient)
  end

  def work_on_child(patient)
    use_bubble_gum_toothpaste(patient)
    give_toothbrush_to(patient)
  end

  private
  def drill_as_hard_as_you_can(patient)
    puts "Drilling very hard! on #{patient}"
  end

  def use_bubble_gum_toothpaste(patient)
    puts "Heard you like bubble gum?"
  end

  def give_toothbrush_to(patient)
    puts "Here's a free toothbrush!"
  end
end

class Adult
  def dispatch_work(doctor)
    puts "dispatch_work called on an adult"
    doctor.work_on_adult(self)
  end
end

class Child
  def dispatch_work(doctor)
    puts "dispatch_work called on an child"
    doctor.work_on_child(self)
  end
end

p1 = Adult.new
c1 = Child.new

d1 = Dentist.new
d1.work_on p1
d1.work_on c1

d2 = Doctor.new
d2.work_on p1
```

### Addendum (3/7/2024): Understanding Double Dispatch

In software development, particularly in object-oriented programming, handling complex interactions between different types of objects can be challenging. One such scenario arises when we need to perform computations that involve multiple combinations of object types. In languages like Ruby, which lack native support for method overloading, we often rely on patterns like double dispatch to address these challenges.

**Understanding Double Dispatch:**

Double dispatch is a design pattern that allows us to dynamically dispatch method calls based on the types of two objects involved in a computation. It involves a two-step process:

1. **First Dispatch:** The method call is dispatched based on the type of the first object.
2. **Second Dispatch:** Within the method called in the first dispatch, another method call is dispatched based on the type of the second object.

This approach effectively decouples the logic for handling different combinations of object types, leading to cleaner and more maintainable code.

**Possible Alternative:**

Alternatively, we could refactor the code to use duck typing and interface extraction. This approach involves defining a `Patient` interface with a `do_work` method, which both `Adult` and `Child` classes implement. The `Doctor` and `Dentist` classes then directly call the `do_work` method on patient objects, eliminating the need for double dispatch.

```ruby
# Define an interface for patients
module Patient
  def do_work(doctor)
    raise NotImplementedError, "This method must be implemented by subclasses"
  end
end

# Define classes for Adult and Child patients implementing the Patient interface
class Adult
  include Patient

  def do_work(doctor)
    doctor.work_on_adult(self)
  end
end

class Child
  include Patient

  def do_work(doctor)
    doctor.work_on_child(self)
  end
end

# Define classes for Doctor and Dentist
class Doctor
  def work_on_adult(adult)
    puts "Checking all your adult parts"
  end

  def work_on_child(child)
    assure_presence_of(child.guardian)
    ask_questions_to(child.guardian)
    puts "Checking all your child parts"
    give_cheap_toy_to(child)
  end

  private

  def assure_presence_of(guardian)
    # Logic to assure the presence of a guardian
  end

  def ask_questions_to(guardian)
    # Logic to ask questions to the guardian
  end

  def give_cheap_toy_to(child)
    puts "Here's a free toy for you!"
  end
end

class Dentist
  def work_on_adult(adult)
    puts "Drilling very hard!"
  end

  def work_on_child(child)
    puts "Using bubble gum toothpaste"
    puts "Here's a free toothbrush for you!"
  end
end

# Usage
p1 = Adult.new
c1 = Child.new

d1 = Dentist.new
d1.work_on p1
d1.work_on c1

d2 = Doctor.new
d2.work_on p1
```

This refactoring promotes a more flexible and maintainable design, aligning with the Interface Segregation Principle (ISP) of the SOLID principles.

In summary, double dispatch is a powerful design pattern for handling complex interactions between objects in object-oriented systems. By leveraging double dispatch effectively, developers can write cleaner, more maintainable code that is better suited to handle the intricacies of real-world applications.
