---
layout: post
title:  "JS Map Implementation"
category: "Javascript"
comments: true
---
This is my answer to one of the [questions from Quora](https://www.quora.com/How-do-you-judge-a-good-JavaScript-developer-with-just-5-questions) I stumbled upon concerning how to judge a good JS dev.

"JavaScript is a functional programming language. Give me an example of how you can use higher order functions in JavaScript to iterate over and apply a function to every element in an array. Do not use a for or while loop."

I didn't find that this particular challenge noted much advance knowledge of JS. But some key things it does touch on are adding prototype functions, loss of functional scope of 'this', and basic idea of how recursion works. Note: I am using some ES6 features and wrote it via a Jasmine test.

```javascript
describe("map recursive implementation", () => {
  it("applies function over array", () => {

     // Let's add our function directly to all Array's via prototype
     // So we can make calls like [1,2,3].myMap(...)
     Array.prototype.myMap = function myMap(callback) {
      // function implicitly binded to the original calling object
      // i.e. [1,5,10,15].myMap(...)
      // therefore 'this' is equal to the array
      // so we can save this to a new variable called arr
      let arr = this;
      let newArray = [];

      function map(arr) {
        if(arr.length === 0) {
          console.log("DONE processing, new array is " + newArray)
          console.log(newArray.length);
          return newArray;
        }
        else {
          //process the head first
          console.log("processing head of array: " + arr[0])
          console.log("pushing: " + callback(arr[0]))
          newArray.push(callback(arr[0]))

          //process the rest of the list
          arr.shift()
          console.log("processing rest of list: " + arr)

          //recursive call here
          //we pass the new array which removed first processed item
          return map(arr, callback);
        }
      }

      return map(this);
    }


    let doubles = [1,5,10,15].myMap(function(x) {
      return x * 2;
    });

    expect(doubles).toEqual([2,10,20,30])
  })
})
```
