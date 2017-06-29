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

```elm
import Color exposing (..)
import Collage exposing (..)
import Element exposing (..)
import Html exposing (..)


-- MODEL
{- We don't really need a useful model here yet so I am creating a
model that is an empty record with a type alias of Game -}

type alias Game = {}

initialModel : Game
initialModel = {}

-- VIEW
{- We use the collage function which is is defined as
collage : Int -> Int -> List Form -> Element

The first two arguments are the size of our canvas. The third argument
is a list of Forms which in our case simply consists a single rectangle
Shape which is transformed into a Form when piped into the filled
function. These are all then piped back into the toHtml function to
convert into something the view can render.
-}

(gameWidth, gameHeight) = (600, 400)

view : Game -> Html msg
view initialModel =
  toHtml <|
    collage gameWidth gameHeight
      [ rect 300 200
          |> filled (rgb 64 224 208)
      ]

-- MAIN
{- Notice the program's update function. Since this is just a static
drawing for now there is really no need to define one. We can simply
pass in an anonymous function that satifies the function type -}

main =
  Html.program { init = (initialModel, Cmd.none)
               , view = view
               , update = (\_ model -> (model, Cmd.none))
               , subscriptions = (\_ -> Sub.none)
               }
```

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
