---
layout: post
title: "Creating a Retro CSS Glitch Text Effect"
categories: ["CSS", "Javascript"]
comments: true
---

Remember those corrupted VHS tapes where the image would tear and shift with weird colors? Here's how to recreate that effect with CSS.

## See It In Action

<div id="glitch-demo" style="background: #000; padding: 40px; text-align: center; margin: 20px 0; border-radius: 8px; overflow: hidden; position: relative;">
  <style>
    #glitch-demo .glitch {
      font-size: 2.5rem;
      font-family: 'Courier New', monospace;
      font-weight: bold;
      color: #fff;
      text-shadow: 
        2px 2px 0 #ff00ff,
        -2px -2px 0 #00ffff;
      position: relative;
      animation: glitch 2s infinite;
      display: inline-block;
    }

    #glitch-demo .glitch::before,
    #glitch-demo .glitch::after {
      content: attr(data-text);
      position: absolute;
      left: 0;
      top: 0;
      width: 100%;
      height: 100%;
    }

    #glitch-demo .glitch::before {
      animation: glitch-1 0.5s infinite;
      color: #ff00ff;
      z-index: -1;
    }

    #glitch-demo .glitch::after {
      animation: glitch-2 0.5s infinite;
      color: #00ffff;
      z-index: -2;
    }

    @keyframes glitch {
      0%, 100% { text-shadow: 2px 2px 0 #ff00ff, -2px -2px 0 #00ffff; }
      25% { text-shadow: -2px 2px 0 #ff00ff, 2px -2px 0 #00ffff; }
      50% { text-shadow: 2px -2px 0 #ff00ff, -2px 2px 0 #00ffff; }
      75% { text-shadow: -2px -2px 0 #ff00ff, 2px 2px 0 #00ffff; }
    }

    @keyframes glitch-1 {
      0%, 100% { clip-path: inset(0 0 0 0); transform: translate(0); }
      20% { clip-path: inset(0 0 50% 0); transform: translate(-5px); }
      40% { clip-path: inset(50% 0 0 0); transform: translate(5px); }
      60% { clip-path: inset(0 0 0 0); transform: translate(0); }
    }

    @keyframes glitch-2 {
      0%, 100% { clip-path: inset(0 0 0 0); transform: translate(0); }
      20% { clip-path: inset(50% 0 0 0); transform: translate(5px); }
      40% { clip-path: inset(0 0 50% 0); transform: translate(-5px); }
      60% { clip-path: inset(0 0 0 0); transform: translate(0); }
    }
  </style>
  <h1 class="glitch" data-text="GLITCH EFFECT!">GLITCH EFFECT!</h1>
</div>

## The Trick

Start with this HTML:

```html
<h1 class="glitch" data-text="GLITCH EFFECT!">GLITCH EFFECT!</h1>
```

That `data-text` attribute? We'll use it to create ghost copies of the text. First, give your text that classic red/blue shift from old CRT monitors:

```css
.glitch {
  font-size: 2.5rem;
  font-weight: bold;
  color: #fff;
  text-shadow: 
    2px 2px 0 #ff00ff,    /* Magenta shadow */
    -2px -2px 0 #00ffff;  /* Cyan shadow */
  position: relative;
  animation: glitch 2s infinite;
}
```

Now here's where it gets fun. Use pseudo-elements to stack two more copies of the text:

```css
.glitch::before,
.glitch::after {
  content: attr(data-text);
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
}

.glitch::before {
  animation: glitch-1 0.5s infinite;
  color: #ff00ff;
  z-index: -1;
}

.glitch::after {
  animation: glitch-2 0.5s infinite;
  color: #00ffff;
  z-index: -2;
}
```

The `content: attr(data-text)` is doing the heavy lifting here. It grabs the text from that data attribute we set up. Now you've got three layers of text ready to glitch out.

For the main text, animate those shadow positions to create movement:

```css
@keyframes glitch {
  0%, 100% { text-shadow: 2px 2px 0 #ff00ff, -2px -2px 0 #00ffff; }
  25% { text-shadow: -2px 2px 0 #ff00ff, 2px -2px 0 #00ffff; }
  50% { text-shadow: 2px -2px 0 #ff00ff, -2px 2px 0 #00ffff; }
  75% { text-shadow: -2px -2px 0 #ff00ff, 2px 2px 0 #00ffff; }
}
```

But the real magic happens with `clip-path`. This is what creates that digital tearing effect:

```css
@keyframes glitch-1 {
  0%, 100% { 
    clip-path: inset(0 0 0 0); 
    transform: translate(0); 
  }
  20% { 
    clip-path: inset(0 0 50% 0);
    transform: translate(-5px);
  }
  40% { 
    clip-path: inset(50% 0 0 0);
    transform: translate(5px);
  }
  60% { 
    clip-path: inset(0 0 0 0); 
    transform: translate(0); 
  }
}
```

`clip-path: inset()` chops off parts of the text. `inset(0 0 50% 0)` hides the bottom half, `inset(50% 0 0 0)` hides the top. Combine that with some horizontal shifts and you get that corrupted video look.

## Making It Your Own

Want a subtle glitch? Slow down the animations. Want chaos? Speed them up to 0.2s. The sweet spot is usually around 0.5s for the pseudo-elements.

Different color combos work great too. Try green-on-green for that terminal look, or go full cyberpunk with purple and yellow. The key is high contrast. You want those layers to pop.

If you really want to sell the effect, add some JavaScript to trigger random intense glitches:

```javascript
setInterval(() => {
  if (Math.random() > 0.7) {
    glitchElement.style.animation = 'glitch 0.2s infinite';
    setTimeout(() => {
      glitchElement.style.animation = 'glitch 2s infinite';
    }, 200 + Math.random() * 300);
  }
}, 3000);
```

## Quick Notes

`clip-path` works everywhere that matters. If you're worried about performance, stick to one or two glitch elements per page. Three layers of animated text can get heavy.

Oh, and for accessibility, kill the animations for people who prefer reduced motion:

```css
@media (prefers-reduced-motion: reduce) {
  .glitch,
  .glitch::before,
  .glitch::after {
    animation: none !important;
  }
}
```

That's it. Pure CSS, no libraries, just some clever use of pseudo-elements and animations. Perfect for headers, loading screens, or anywhere you want that corrupted digital aesthetic.