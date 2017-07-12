---
layout: post
title:  "Drawing Graphics in Elm"
category: "Elm"
comments: true
---
I'm learning how to write games in Elm and there does not seem to be
very many resources updated for Elm 0.18. The old `Graphics` module has
been moved out of elm-lang/core and into evancz/elm-graphics which might
cause some confusion/compilation errors when looking at older examples.

The elm-graphics package gives us modules that interface with HTML 5
Canvas API. So lets see how we can draw something basic to the browser.
In my later posts we will continue to build upon this program.

Make sure you have the required packages installed in your project
directory:
```
elm package install elm-lang/html
elm package install evancz/elm-graphics
```

<script src="https://gist.github.com/sngeth/4b4004a8a284b66eb0c22339162857e5.js"></script>

### Summary:
We learned how to render a "canvas" on the screen by using
Element.toHtml which takes an Element created by Collage.collage.
While the Collage mainly deals with free form graphics, the Element and
Text Modules can help you plug in various other types of graphics into
your collage once converted into a form. I recommend checking out the
[elm-graphics](http://package.elm-lang.org/packages/evancz/elm-graphics/1.0.1/)
documentation to see what other Forms you can create in your collages.
So far, drawing graphics to the screen may seem somewhat tedious as it is
in most other libraries. Elm's architecture will start to shine in its
simplicity in how updates and events are handled in your app.
