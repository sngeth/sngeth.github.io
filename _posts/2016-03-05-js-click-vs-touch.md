---
layout: post
title:  "Javascript click vs touch events"
comments: true
---
If your application needs to respond to both mobile touches and desktop
clicks you could write the following

```javascript
function bind_button(selector, subselector) {
  $(selector).on('click', subselector, function(event) {
    handleEvent();
    return false;
  });

  if('touchstart' in window) {
    $(selector).on('touchstart', subselector, function(event) {
      handleEvent();
      return false;
    });
  }
}
```
