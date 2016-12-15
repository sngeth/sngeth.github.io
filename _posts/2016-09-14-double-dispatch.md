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
