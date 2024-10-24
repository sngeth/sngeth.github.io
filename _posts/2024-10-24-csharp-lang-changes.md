---
layout: post
title: "C# Evolution: A Practical Implementation Guide (6.0 to 12.0)"
category: "C#"
comments: true
---

C# 6.0 marked my introduction to the language. After going back to full time professional Ruby development, it seems i've missed quite a bit.
Features like tuples and pattern matching, which I don't recall using, are particularly fun from other languages.
The full [history of changes](https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-version-history) can be found here
but I'd appreciate insights on any other important day-to-day concepts I might have overlooked.

## Table of Contents
1. [C# 6.0 (2015)](#c-60-2015)
2. [C# 7.0 (2017)](#c-70-2017)
3. [C# 8.0 (2019)](#c-80-2019)
4. [C# 9.0 (2020)](#c-90-2020)
5. [C# 10.0 (2021)](#c-100-2021)
6. [C# 11.0 (2022)](#c-110-2022)
7. [C# 12.0 (2023)](#c-120-2023)

## C# 6.0 (2015)
Focus on developer productivity and code readability.

### String Interpolation
```csharp
// Old way
string message = string.Format("Hello {0}, you are {1} years old", name, age);

// New way
string message = $"Hello {name}, you are {age} years old";
string complex = $"Math: {2 + 2}, Method: {CalculateValue()}";
```
**When to use**: Any time you need to embed values or expressions within strings
**Why use it**:
- More readable than string.Format()
- Compile-time checking of interpolated values
- IntelliSense support for embedded expressions

**Best practices**:
- Use for simple string formatting
- Consider traditional format strings for complex formatting scenarios
- Be careful with complex expressions - extract to variables if they become hard to read

### Null Propagation (?.)
```csharp
// Old way
var zipCode = customer != null
    ? customer.Address != null
        ? customer.Address.ZipCode
        : null
    : null;

// New way
var zipCode = customer?.Address?.ZipCode;
var length = customer?.Name?.Length ?? 0;
```
**When to use**:
- Accessing properties or methods on potentially null objects
- Chaining multiple null-checkable operations

**Why use it**:
- Eliminates verbose null-checking code
- Prevents null reference exceptions
- Makes code more readable

**Best practices**:
- Combine with ?? operator for default values
- Don't overuse - if you find too many null checks, consider redesigning

## C# 7.0 (2017)
Introduction of tuples and pattern matching.

### Tuples
```csharp
// Method returning multiple values
public (string name, int age) GetPersonDetails()
{
    return ("John", 30);
}

// With deconstruction
var (name, age) = GetPersonDetails();

// Tuple usage in LINQ
var statistics = orders
    .Select(o => (o.Date, o.Total))
    .GroupBy(x => x.Date.Month)
    .Select(g => (month: g.Key, total: g.Sum(x => x.Total)));
```
**When to use**:
- Returning multiple values from methods
- Temporary grouping of related data
- LINQ projections

**Why use it**:
- Cleaner than out parameters
- More structured than anonymous types
- Better performance than small classes

**Best practices**:
- Name tuple elements for clarity
- Use for internal implementation details
- Consider proper classes for public APIs

### Pattern Matching
```csharp
// Type patterns with when
switch (shape)
{
    case Circle c when c.Radius > 10:
        return $"Large circle: {c.Radius}";
    case Rectangle r when r.Width == r.Height:
        return "Square";
    case Rectangle r:
        return $"Rectangle: {r.Width}x{r.Height}";
    case null:
        throw new ArgumentNullException(nameof(shape));
    default:
        return "Unknown shape";
}

// Property patterns
if (order is { Status: OrderStatus.Paid, Total: > 1000 })
{
    // Process premium order
}
```
**When to use**:
- Type checking and casting in one operation
- Complex conditional logic
- Object property validation

**Why use it**:
- More concise than traditional type checking
- Safer than manual casting
- More maintainable than nested if statements

## C# 8.0 (2019)
Focus on null safety and improved patterns.

### Nullable Reference Types
```csharp
#nullable enable

public class Customer
{
    public string Name { get; set; } = null!; // Must be initialized
    public string? MiddleName { get; set; }   // Can be null

    public string GetFullName(string? title)
    {
        return title is null
            ? Name
            : $"{title} {Name}";
    }
}
```
**When to use**:
- New projects where null safety is important
- Gradually in existing projects
- APIs where null semantics matter

**Why use it**:
- Catches null reference bugs at compile time
- Makes null handling intentions clear
- Improves code documentation

### Switch Expressions
```csharp
public decimal CalculateDiscount(Customer customer) =>
    customer.Type switch
    {
        CustomerType.New => 0.1m,
        CustomerType.Regular when customer.Orders.Count > 100 => 0.2m,
        CustomerType.Regular => 0.15m,
        CustomerType.VIP => 0.3m,
        _ => throw new ArgumentException($"Unknown customer type: {customer.Type}")
    };
```
**When to use**:
- Converting one type to another based on conditions
- Simple pattern matching scenarios
- Replacing switch statements with expressions

**Why use it**:
- More concise than switch statements
- Forces exhaustive matching
- Better type safety

## C# 9.0 (2020)

### Records
```csharp
// Immutable record
public record Person(string Name, int Age);

// Record with additional members
public record Employee(string Name, int Age, string Department)
{
    public bool IsManager { get; init; }
    public decimal CalculateBonus() => IsManager ? 5000m : 1000m;
}

// Inheritance
public record Manager(string Name, int Age, string Department)
    : Employee(Name, Age, Department)
{
    public int TeamSize { get; init; }
}
```
**When to use**:
- Data-centric types
- Domain models
- DTOs
- Immutable objects

**Why use it**:
- Built-in value equality
- Immutability by default
- Concise syntax for data classes

**Best practices**:
- Use for immutable data models
- Consider inheritance hierarchy
- Use with pattern matching

## C# 10.0 (2021)

### Global Using Directives
```csharp
// In a central file (e.g., GlobalUsings.cs)
global using System.Collections.Generic;
global using System.Linq;
global using System.Text.Json;
global using static System.Math;

// File scoped namespaces
namespace MyApp;

public class Program { }
```
**When to use**:
- Common imports across many files
- Framework-specific imports
- Large projects with consistent dependencies

**Why use it**:
- Reduces code repetition
- Centralizes dependency management
- Cleaner source files

## C# 11.0 (2022)

### Raw String Literals
```csharp
var json = """
    {
        "name": "John Doe",
        "age": 30,
        "addresses": [
            {
                "type": "home",
                "street": "123 Main St"
            }
        ]
    }
    """;

var sql = """
    SELECT u.Name, u.Email
    FROM Users u
    WHERE u.Status = 'Active'
        AND u.LastLoginDate >= @date
    """;
```
**When to use**:
- JSON templates
- SQL queries
- HTML/XML content
- Any multi-line string with special characters

**Why use it**:
- No escape sequences needed
- Preserves formatting
- More readable

## C# 12.0 (2023)

### Primary Constructors
```csharp
public class CustomerService(
    ILogger logger,
    IRepository repository,
    IValidator validator)
{
    public async Task<Customer> CreateCustomer(CustomerDto dto)
    {
        logger.Log("Creating customer");

        if (!validator.Validate(dto))
            throw new ValidationException();

        var customer = new Customer(dto);
        await repository.Save(customer);
        return customer;
    }
}
```
**When to use**:
- Service classes with dependencies
- Classes with simple initialization
- When constructor parameters are used throughout the class

**Why use it**:
- Reduces boilerplate
- Clear dependency declaration
- Improved readability

### Collection Expressions
```csharp
// Array initialization
int[] numbers = [1, 2, 3, 4, 5];

// List creation with spread operator
var existing = new List<int> { 1, 2, 3 };
var combined = [..existing, 4, 5, 6];

// Dictionary initialization
var config = new Dictionary<string, int>
{
    ["MaxRetries"] = 3,
    ["Timeout"] = 1000
};
```
**When to use**:
- Simple collection initialization
- Combining collections
- Creating fixed-size arrays

**Why use it**:
- More concise syntax
- Clearer intent
- Reduced ceremony
