---
layout: post
title:  "Extract Interface"
comments: true
---
Note: The sample code in this post is from Feathers' book Working Effectively With
Legacy Code which i'm trying to read through and summarize my knowledge.

Sometimes your design shows it could use improvement if you notice it's hard to test. When
it's hard to test your code, you eventually won't even bother.

A common thing that occurs is when you try to put a class under test it
has dependencies/collaborating classes which need to be created. Below
the Sale class depends on a ArtR56Display class.

```java
public class Sale {
  public void scan() {
      ArtR56Display display = new ArtR56Display();
      display.showLine();
    }
  }
}
```

First, we need to use dependency injection on the display object. One
easy way to do this is by passing it through the constructor. Typically instantiating objects
inside another class will highlight dependencies you need to overcome
(although there are exceptions e.g. basic value model objects).


```java
public class Sale {
  private ArtR56Display display;

  public Sale(ArtR56Display display) {
    this.display = display;
  }

  public void scan() {
      display.showLine();
    }
  }
}
```

Now we want to test our sale class. We create a test which will
instantiate a ArtR56Display but suprise, it's connected to physical
cash register. It's not very convenient to write unit tests that rely on
this sort of external dependency just to run. Other typical dependencies
such as DB connections also suffer from this issue.

So the solution here is to extract the display to an interface which has
the side effect of promoting loose coupling and replaceability. It
allows the Sale class to be extended but not modified. So in the future
our Sale class can be hooked up it any other type of display.


```java
public interface Display
{
  void showLine(String line);
}

public class Sale
{
  private Display display;

  public Sale(Display display) {
    this.display = display;
  }

  public void scan() {
    ...
    String itemLine = item.name() + " " + item.price().asDisplayText();
    display.showLine(itemLine);
  }
}
```

At this point we could create a FakeDisplay that implements showLine().
In our tests now we can inject our FakeDisplay and still test the scan
method to ensure it still sends the right text to the display when the
Sale class is used without depending on the physical cash register.

```java
public class FakeDisplay implements Display {
  private String lastLine = "";

  public void showLine(String line) {
    lastLine = line;
  }

  public String getLastLine() {
    return lastLine;
  }
}
```

As a side note most Mocking libraries can handle most of this stuff for us
by creating a proxy class for any interfaces we would like to
fake and configuring it to execute dummy behavior.
