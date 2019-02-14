---
layout: post
title:  "Hexagonal Architecture"
comments: true
---
What kind of application can be monolithic but still be written with a
well maintained and clean code base? The hexagonal architecture is
probably the most common one I've seen in my experience where the goal
is to separate business logic from various adapters that implement UIs
and integrate with external systems. One of the nice benefits of this
architecture is when you need to keep business logic but swap out your
front end, database, etc, i.e. separation of concerns.

Some of the basic benefits of this are that it's easy to develop and
make quick changes since "you have everything you need".

My favorite benefit of this style is that it's straightforward to test
and deploy. Writing end to end tests are usually trivial with good
testing frameworks. Deployment usually consists of just copying a WAR
file to a web server or using a single command push to cloud-based
infrastructure.

In the next posts, I hope to break down in more detail why the hexagonal
architecture tends to break down (or if that's even really the case)
despite being modular and clean.
