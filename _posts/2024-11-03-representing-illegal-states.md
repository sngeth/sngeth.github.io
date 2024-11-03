---
layout: post
title: "Making Invalid States Unrepresentable: From Java to Haskell"
category: "Haskell"
comments: true
---
## Introduction

Recently, I came across an interesting [example](https://x.com/java/status/1852358690466075124) on X that demonstrates this concept using Java. Let's explore how we can take this further using Haskell's type system.

## The Java Approach

Here's the original Java code:

```java
record Book(String title, ISBN isbn, List<Author> authors) {
    Book {
        Objects.requireNonNull(title);
        if (title.isBlank())
            throw new IllegalArgumentException("Title must not be blank");

        Objects.requireNonNull(isbn);
        Objects.requireNonNull(authors);
        if (authors.isEmpty())
            throw new IllegalArgumentException("There must be at least one author");

        // plus immutable copies as in the previous article
    }
}
```

This code does enforce our business rules:
1. Title cannot be null or blank
2. ISBN cannot be null
3. Authors list cannot be null or empty

However, there are several issues with this approach:

1. **Runtime Validation**: All checks happen at runtime. We won't know about invalid data until the program is running.
2. **Defensive Programming**: We need to manually check for all invalid cases.
3. **Documentation Required**: Nothing in the type signature tells us about these constraints.
4. **Partial Functions**: The constructor can fail at runtime.

## The Haskell Approach

Let's see how we can use Haskell's type system to enforce these rules at compile time while adding additional type safety:

```haskell
{-# LANGUAGE OverloadedStrings #-}
{-# LANGUAGE RecordWildCards #-}
{-# LANGUAGE StrictData #-}

module Main where

import Control.Monad (when)
import Data.Text (Text)
import qualified Data.Text as T
import Data.List.NonEmpty (NonEmpty(..))
import qualified Data.List.NonEmpty as NE
import Data.Char (isDigit, isSpace)

-- New ISBN newtype for type safety
newtype ISBN = ISBN { unISBN :: Text }
  deriving (Show, Eq)

-- New Author newtype for type safety
newtype Author = Author { unAuthor :: Text }
  deriving (Show, Eq)

-- Improved Book type with newtypes
data Book = Book
  { bookTitle   :: !Text      -- Strict fields
  , bookISBN    :: !ISBN      -- Using ISBN newtype
  , bookAuthors :: !(NonEmpty Author)  -- Using Author newtype
  } deriving Show

-- Smart constructor for ISBN
mkISBN :: Text -> Either String ISBN
mkISBN text = do
  when (T.null text) $
    Left "ISBN must not be blank"
  let digits = T.filter isDigit text
  if T.length digits == 13 && T.all isDigit digits
    then Right $ ISBN text
    else Left "ISBN must be 13 digits"

-- Smart constructor for Author
mkAuthor :: Text -> Either String Author
mkAuthor text =
  if T.null text || T.all isSpace text
    then Left "Author name cannot be blank"
    else Right $ Author text

-- Smart constructor for NonEmpty list of authors
mkAuthors :: [Text] -> Either String (NonEmpty Author)
mkAuthors [] = Left "There must be at least one author"
mkAuthors texts = do
  authors <- traverse mkAuthor texts
  case authors of
    [] -> Left "There must be at least one author"  -- Should never happen due to previous check
    (a:as) -> Right $ a :| as

-- Smart constructor for Book
mkBook :: Text -> Text -> [Text] -> Either String Book
mkBook titleText isbnText authorTexts = do
  -- Title validation
  when (T.null titleText || T.all isSpace titleText) $
    Left "Title must not be blank"

  -- ISBN validation using smart constructor
  isbn <- mkISBN isbnText

  -- Authors validation using smart constructor
  authors <- mkAuthors authorTexts

  -- Create the book if all validations pass
  Right $ Book
    { bookTitle = titleText
    , bookISBN = isbn
    , bookAuthors = authors
    }
```

### Key Improvements

1. **Stronger Type Safety**
   - Introduced `ISBN` and `Author` newtypes to prevent mixing up text fields
   - Each domain type has its own smart constructor with validation
   - Strict fields for better performance

2. **NonEmpty List for Authors**
   - Guarantees at least one author at the type level
   - No runtime checks needed for non-emptiness
   - Makes the constraint explicit in the type signature

3. **Smart Constructors with Validation**
   - Separate validation logic for each domain type
   - Composable validation using `Either`
   - Clear error messages for each validation failure

4. **Type-Level Guarantees**
   - Once a `Book` exists, we know it's valid
   - Invalid states are impossible to represent
   - Compiler enforces our domain rules

Here's an example of using this improved implementation:

```haskell
{-# LANGUAGE OverloadedStrings #-}
{-# LANGUAGE RecordWildCards #-}
{-# LANGUAGE StrictData #-}

module Main where

import Control.Monad (when)
import Data.Text (Text)
import qualified Data.Text as T
import Data.List.NonEmpty (NonEmpty(..))
import qualified Data.List.NonEmpty as NE
import Data.Char (isDigit, isSpace)

-- Domain Types
newtype ISBN = ISBN { unISBN :: Text }
  deriving (Show, Eq)

newtype Author = Author { unAuthor :: Text }
  deriving (Show, Eq)

data Book = Book
  { bookTitle   :: !Text
  , bookISBN    :: !ISBN
  , bookAuthors :: !(NonEmpty Author)
  } deriving Show

-- Smart Constructors
mkISBN :: Text -> Either String ISBN
mkISBN text = do
  when (T.null text) $
    Left "ISBN must not be blank"
  let digits = T.filter isDigit text
  if T.length digits == 13 && T.all isDigit digits
    then Right $ ISBN text
    else Left "ISBN must be 13 digits"

mkAuthor :: Text -> Either String Author
mkAuthor text =
  if T.null text || T.all isSpace text
    then Left "Author name cannot be blank"
    else Right $ Author text

mkAuthors :: [Text] -> Either String (NonEmpty Author)
mkAuthors [] = Left "There must be at least one author"
mkAuthors texts = do
  authors <- traverse mkAuthor texts
  case authors of
    [] -> Left "There must be at least one author"
    (a:as) -> Right $ a :| as

mkBook :: Text -> Text -> [Text] -> Either String Book
mkBook titleText isbnText authorTexts = do
  when (T.null titleText || T.all isSpace titleText) $
    Left "Title must not be blank"

  isbn <- mkISBN isbnText
  authors <- mkAuthors authorTexts

  Right $ Book
    { bookTitle = titleText
    , bookISBN = isbn
    , bookAuthors = authors
    }

-- Helper function to display validation result
displayResult :: Either String Book -> IO ()
displayResult result = case result of
  Left err -> putStrLn $ "Error: " ++ err
  Right book -> putStrLn $ "Successfully created book: " ++ show book

-- Main function with test cases
main :: IO ()
main = do
  putStrLn "Testing book validation..."
  putStrLn "\n1. Valid book:"
  displayResult $ mkBook "Dune" "9780441172719" ["Frank Herbert"]

  putStrLn "\n2. Valid book with multiple authors:"
  displayResult $ mkBook "Good Omens" "9780441172719" ["Terry Pratchett", "Neil Gaiman"]

  putStrLn "\n3. Invalid: Empty title:"
  displayResult $ mkBook "" "9780441172719" ["Frank Herbert"]

  putStrLn "\n4. Invalid: Blank title (only spaces):"
  displayResult $ mkBook "   " "9780441172719" ["Frank Herbert"]

  putStrLn "\n5. Invalid: Wrong ISBN format:"
  displayResult $ mkBook "Dune" "123" ["Frank Herbert"]

  putStrLn "\n6. Invalid: No authors:"
  displayResult $ mkBook "Dune" "9780441172719" []

  putStrLn "\n7. Invalid: Blank author name:"
  displayResult $ mkBook "Dune" "9780441172719" ["  "]

  putStrLn "\n8. Invalid: Mix of valid and invalid authors:"
  displayResult $ mkBook "Dune" "9780441172719" ["Frank Herbert", "", "Kevin J. Anderson"]

  putStrLn "\n9. Invalid: Non-numeric ISBN:"
  displayResult $ mkBook "Dune" "abc0441172719" ["Frank Herbert"]

  putStrLn "\n10. Valid: ISBN with hyphens (still has 13 digits):"
  displayResult $ mkBook "Dune" "978-0441172719" ["Frank Herbert"]
```

### Benefits of This Approach

1. **Type-Level Guarantees**
   - Domain rules enforced by the compiler
   - No need for defensive programming
   - Invalid states are unrepresentable

2. **Self-Documenting Code**
   - Types clearly indicate constraints
   - Newtypes make the domain model explicit
   - Smart constructors document validation rules

3. **Better Error Handling**
   - Validation results are explicit in return types
   - No runtime exceptions
   - Composable error handling

4. **Maintainability**
   - Easy to add new constraints
   - Validation rules are reusable
   - Type system catches errors at compile time

## Conclusion

While the Java solution enforces business rules through runtime checks and exceptions, our improved Haskell approach pushes these checks to the type system and makes invalid states truly unrepresentable. The addition of newtypes and strict fields further enhances type safety and performance.

Key takeaways:
1. Use types to encode business rules when possible
2. Push validation to the boundaries of your system
3. Make impossible states impossible, not just checked
4. Let the compiler help you enforce your domain rules
5. Use newtypes to prevent mixing up similar types
6. Make data structures strict when appropriate

The end result is a system that's not only safer but also more maintainable and self-documenting.
