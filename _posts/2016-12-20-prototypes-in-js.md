---
layout: post
title:  "Prototypes in Javascript"
category: "Javascript"
comments: true
---
## What is a prototype?

An object that exists on every function in javascript.

A function's prototype: A function's prototype is the object instance
that will become the prototype for all objects created using this
function as a constructor

An object's prototype: An object's prototype is the object instance from
which the object is inherited.

```javascript
var myFunc = function() {}
console.log(myFunc.prototype) // empty protototype object

var cat = {name: 'Fluffy'}
console.log(cat.__proto__); // note objects don't have a prototype but have a __proto__ object

function Cat(name, color) {
  this.name = name
  this.color = color
}

var fluffy = new Cat('Fluffy', 'White')

Cat.prototype.age = 3

console.log(Cat.prototype) // has a property age: 3
console.log(fluffy.__proto__) // has a property age: 3
console.log(Cat.prototype === fluffy.__proto__) // true - same prototype instance

var muffin = new Cat('Muffin', 'Brown')
console.log(muffin.__proto__) // has a property age: 3


fluffy.age = 4

//instance properties override prototype properties
console.log(fluffy.age) // 4
console.log(fluffy.__proto__.age) // 3

delete fluffy.age
console.log(fluffy.age) // 3 - looks up prototype chain

//Changing a Function's prototype
Cat.prototype = {age: 5}

var snowbell = new Cat('Snowbell', 'White')

console.log(fluffy.age) // 3 still refers to original prototype instance
console.log(muffin.age) // 3 still refers to original prototype instance
console.log(snowbell.age) // 5 gains new defined prototype
console.log(snowbell.age) // 5 gains new defined prototype

//Prototype chains
console.log(fluffy.__proto__) // Cat { age: 4 }
console.log(fluffy.__proto__.__proto__) // Object {}
console.log(fluffy.__proto__.__proto__.__proto__) // null
```

## Prototypical inheritance

```javascript
function Animal(voice) {
  this.voice = voice || 'grunt'
}

Animal.prototype.speak = function() {
  console.log('Grunt')
}

function Cat(name, color) {
  //call parent constructor for parent related initialization
  Animal.call(this, 'Meow')
  this.name = name
  this.color = color
}

Cat.prototype = Object.create(Animal.prototype) // Link the prototypes
Cat.prototype.constructor = Cat // Necessary to correct prototype chain references

var fluffy = new Cat('Fluffy', 'White')

fluffy.speak() // 'Grunt'
```

## Inheritance using new ES6 class syntax
We have some syntatic sugar that makes it cleaner to set up inheritance

```javascript
class Animal {
  constructor(voice) {
    this.voice = voice || 'grunt'
  }

  speak() {
    console.log(this.voice)
  }
}

class Cat extends Animal {
  constructor(name, color) {
    super('Meow')
    this.name = name
    this.color = color
  }
}

var fluffy = new Cat('Fluffy', 'White')
fluffy.speak() // "Meow"
```

An important note is that the constructor object is a class not a constructor
function on the object.

Also, members of classes are not enumerable by default. E.g., the speak
function will not show up on the Object.keys or loop over the properties
of the Animal class.
