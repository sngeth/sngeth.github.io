---
layout: post
title:  "Escaping Monolithic Hell"
comments: true
---
Some of my thoughts when reading the first chapter of Microservice Patterns
book: Escaping from Monolithic Hell

It seems that one characteristic of a system exhibiting "monolithic
hell" would be that it's a large, complex application i.e. single Java
WAR. So what? Large and complex is not mutually exclusive with a
"monolithic hell" app. It could just mean the the business domain has a
very large set of rules, principles, or logic.

Not only are they large and complex, but they've deemed it to be a big
ball of mud. So what exactly is a big ball of mud?

"A BIG BALL OF MUD is haphazardly structured, sprawling, sloppy,
duct-tape and bailing wire, spaghetti code jungle. We’ve all seen them.
These systems show unmistakable signs of unregulated growth and repeated
expedient repair. Information is shared promiscuously among distant
elements of the system, often to the point where nearly all the
important information becomes global or duplicated. The overall
structure of the system may never have been well defined. If it was, it
may have eroded beyond recognition. Programmers with a shred of
architectural sensibility shun these quagmires. Only those who are
unconcerned about architecture, and, perhaps, are comfortable with the
inertia of the day-to-day chore of patching the holes in these failing
dikes, are content to work on such systems."

So a big ball of mud is associated with "spaghetti code", unstructured
and difficult to maintain source code. This inherently means that the
system has no perceivable architecture. Again, I don't believe this is
mutually exclusive to a monolithic app. It's quite believable that one
could create a monolithic app that is structured, maintainable, and
follows a solid design and architectural principles.

"The FTGO application is exhibiting all the symptoms of monolithic
hell." I'm not exactly sure I'm convinced at this point. But for now, I
am going to take a detour and dive into the [Big Ball of Mud](http://www.laputan.org/mud/) paper
since it seems like a good idea to revisit a list of classic architectural
mistakes in software development.
