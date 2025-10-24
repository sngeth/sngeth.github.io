---
layout: post
title: "analyzing ocaml patterns in a real web app: what melange code actually looks like"
date: 2025-10-15
categories: ocaml melange javascript react functional-programming
---

i built an options max pain calculator using melange (ocaml that compiles to javascript). this post analyzes the actual code—what patterns emerge, how the type system shapes the implementation, and what makes functional programming different in practice.

## the project: what is max pain?

the app calculates "maximum pain" for stock options. this is the strike price where option holders (collectively) lose the most money at expiration.

here's how it works:

**the setup**: every option contract has a strike price and open interest (number of contracts outstanding). at expiration, options are worth either:
- **calls**: `max(0, stock_price - strike)` per share (100 shares per contract)
- **puts**: `max(0, strike - stock_price)` per share

**the calculation**: for each possible strike price, calculate total value of all calls + all puts if the stock expires at that price. the strike where this total is minimized is "max pain"—where option holders lose the most.

**why it matters**: some traders believe stocks tend to gravitate toward max pain at expiration due to market maker hedging. whether that's true is debatable, but it's an interesting calculation that requires processing options chain data.

**the algorithm**:
1. fetch all option contracts (calls and puts) for an expiration date
2. extract unique strike prices
3. for each strike, sum up intrinsic value of all options if stock expires there
4. find the strike with minimum total value

live demo: [options-max-pain.pages.dev](https://options-max-pain.pages.dev/)

this problem shows where ocaml differs from javascript/typescript:
- **json parsing**: requires explicit decoders instead of just calling `.json()`
- **data transformations**: immutable pipelines with fold instead of mutable loops
- **error handling**: option types and pattern matching instead of null checks
- **finding the minimum**: explicit handling of empty lists (can't just return undefined)

let's analyze how these patterns appear in the actual code.

## pattern 1: types as documentation

ocaml makes you define your data structures upfront:

```ocaml
type optionContract = {
  strike: float,
  openInterest: int,
  optionType: string, /* "call" or "put" */
};

type painByStrike = {
  strike_price: float,
  call_pain: float,
  put_pain: float,
  total_pain: float,
};

type maxPainResult = {
  strikePrice: float,
  totalPain: float,
  painBreakdown: list(painByStrike),
};
```

**what's different from typescript:**
- these aren't optional annotations you can skip with `any`
- the compiler tracks every field access and ensures consistency
- misspell a field name anywhere? compile error
- try to access a field that doesn't exist? compile error
- no runtime overhead—all this type information gets erased during compilation

this upfront ceremony pays off later. refactoring is mechanical: change a type, follow the compiler errors.

## pattern 2: pipeline composition with the pipe operator

the core calculation looks like this:

```ocaml
let calculateMaxPain = (contracts: list(optionContract)): option(maxPainResult) => {
  /* get unique strike prices */
  let strikes =
    contracts
    |> List.map(c => c.strike)
    |> List.sort_uniq(compare);

  /* calculate pain for each strike */
  let painByStrikeList =
    strikes
    |> List.map(strike => {
         let (callPain, putPain) =
           contracts
           |> List.fold_left(
                (acc, contract) => {
                  let (accCallPain, accPutPain) = acc;
                  switch (contract.optionType) {
                  | "call" =>
                    let pain =
                      strike > contract.strike
                        ? (strike -. contract.strike)
                          *. float_of_int(contract.openInterest)
                          *. 100.0
                        : 0.0;
                    (accCallPain +. pain, accPutPain);
                  | "put" =>
                    let pain =
                      strike < contract.strike
                        ? (contract.strike -. strike)
                          *. float_of_int(contract.openInterest)
                          *. 100.0
                        : 0.0;
                    (accCallPain, accPutPain +. pain);
                  | _ => acc
                  };
                },
                (0.0, 0.0),
              );
         {
           strike_price: strike,
           call_pain: callPain,
           put_pain: putPain,
           total_pain: callPain +. putPain,
         };
       });

  /* find minimum pain strike */
  let minPainStrike =
    painByStrikeList
    |> List.fold_left(
         (minResult, current) =>
           switch (minResult) {
           | None => Some(current)
           | Some(min) =>
             current.total_pain < min.total_pain ? Some(current) : Some(min)
           },
         None,
       );

  /* return result */
  switch (minPainStrike) {
  | None => None
  | Some(minStrike) =>
    Some({
      strikePrice: minStrike.strike_price,
      totalPain: minStrike.total_pain,
      painBreakdown: painByStrikeList,
    })
  };
};
```

**key patterns:**

**pipe operator (`|>`)**: threads data through transformations left-to-right. compare to javascript:
```javascript
// javascript
const strikes = Array.from(
  new Set(contracts.map(c => c.strike))
).sort((a, b) => a - b);

// ocaml with pipes
let strikes =
  contracts
  |> List.map(c => c.strike)
  |> List.sort_uniq(compare);
```

**fold_left for accumulation**: like `reduce()` in javascript, but with explicit accumulator type. the tuple `(accCallPain, accPutPain)` carries both values through the fold. no mutation—each iteration returns a new tuple.

**pattern matching for control flow**: the switch on `optionType` is checked at compile time. the `| _ => acc` case handles unexpected values (though using a string here instead of a variant type is a missed opportunity).

**return type is `option(maxPainResult)`**: this function might not have a result. what if the contracts list is empty? in javascript, you'd return `null` or `undefined` and hope callers check. in ocaml, the return type is explicitly `option(maxPainResult)`:
```ocaml
type option('a) =
  | Some('a)
  | None;
```

callers must pattern match on the result:
```ocaml
switch (calculateMaxPain(contracts)) {
| Some(result) => /* use result.strikePrice */
| None => /* handle empty case */
}
```

the compiler won't let you access `result.strikePrice` without handling the `None` case first. no silent failures, no forgotten null checks.

## pattern 3: composable json decoders

the json parsing code is verbose but interesting:

```ocaml
|> Js.Promise.then_((json) => {
     open Melange_json.Of_json;

     /* compose decoders from small pieces */
     let decodeDetails = (json) => {
       let strikePrice = json |> field("strike_price", float);
       let contractType = json |> field("contract_type", string);
       (strikePrice, contractType);
     };

     let decodeResult = (json) => {
       let (strike, optionType) = json |> field("details", decodeDetails);
       let openInterest = json |> field("open_interest", int);
       {strike, openInterest, optionType};
     };

     try {
       let contracts =
         json
         |> field("results", array(decodeResult))
         |> Array.to_list;

       callback(Ok(contracts));
       Js.Promise.resolve();
     } {
       | Melange_json.Of_json_error(error) => {
         let msg = Melange_json.of_json_error_to_string(error);
         callback(Error("JSON decode error: " ++ msg));
         Js.Promise.resolve();
       }
     };
   })
```

**trade-offs here:**

in typescript, you'd write:
```typescript
const response = await fetch(url);
const data = await response.json();
const contracts = data.results; // hope it's the right shape
```

in ocaml, you build composable decoders:
- `decodeDetails` decodes nested `details` object
- `decodeResult` uses `decodeDetails` to decode each array item
- final decoder: `field("results", array(decodeResult))`

**upside**: if the json doesn't match, you get a specific error: "field 'strike_price' not found" or "expected float, got string". the decoder tells you exactly what failed.

**downside**: you write the structure twice—once in the type definition, once in the decoder. every field requires explicit decoder logic.

**what you gain**: confidence. once decoded, the type system guarantees `contracts` is `list(optionContract)`. no runtime type checking needed anywhere else in the codebase.

## pattern 4: explicit nullability in react

the react component shows how the option type forces explicit error handling:

```ocaml
[@react.component]
let make = () => {
  let (result, setResult) = React.useState(() => None);
  let (error, setError) = React.useState(() => None);

  let handleCalculate = _ => {
    fetchOptionsData(
      ticker,
      expirationDate,
      response => {
        switch (response) {
        | Ok(contracts) =>
          let maxPain = calculateMaxPain(contracts);
          setResult(_ => maxPain);
        | Error(msg) => setError(_ => Some(msg))
        };
      },
    );
  };

  /* render jsx */
  <div>
    {switch (error) {
     | Some(msg) => <p> {React.string("Error: " ++ msg)} </p>
     | None => React.null
     }}
    {switch (result) {
     | Some({strikePrice, totalPain, painBreakdown}) =>
       <div>
         <p> {React.string("$" ++ Js.Float.toFixed(strikePrice))} </p>
       </div>
     | None => React.null
     }}
  </div>;
};
```

**what's happening:**

**state initialization**: `React.useState(() => None)` creates state with an option type. `error` is `option(string)`, `result` is `option(maxPainResult)`. there's no `null` or `undefined`—just `None`.

**pattern matching in jsx**: can't access `result.strikePrice` directly. must pattern match:
```ocaml
switch (result) {
| Some({strikePrice, totalPain, painBreakdown}) => /* use it */
| None => React.null
}
```

the compiler won't let you forget the `None` case.

**explicit string wrapping**: `React.string()` converts ocaml strings to react elements. this looks verbose, but it prevents accidentally rendering objects or functions. in typescript/react:
```typescript
<p>{someObject}</p> // renders "[object Object]"
```

in ocaml:
```ocaml
<p> someObject </p> /* compile error: expected React.element, got object */
```

## what the compiled javascript looks like

melange outputs readable javascript. here's what `calculateMaxPain` compiles to:

```javascript
function calculateMaxPain(contracts) {
  var strikes = List.sort_uniq(Caml_obj.compare, List.map(
    function (c) { return c.strike; },
    contracts
  ));

  var painByStrikeList = List.map(function (strike) {
    var match = List.fold_left(/* ... fold logic ... */, [0.0, 0.0], contracts);
    return {
      strike_price: strike,
      call_pain: match[0],
      put_pain: match[1],
      total_pain: match[0] + match[1]
    };
  }, strikes);

  // ... rest of function
}
```

observations:
- **no type annotations** - all stripped during compilation
- **readable structure** - mirrors the source ocaml
- **minimal runtime** - just a few helper functions for lists and comparisons
- **no null checks** - the compiler already verified everything

the types exist only at compile time. runtime javascript is clean and fast.

## what i learned

**the type system catches real bugs early**

multiple times during development, i refactored the pain calculation logic. each time, the compiler caught every place that needed updating. change a field name? compiler shows every access. change a function signature? compiler shows every call site.

this isn't theoretical. it saved me from shipping broken code.

**json decoding is verbose but worth it**

writing decoders feels like busy work at first. but when the api changed (polygon.io updated their response structure), i got immediate compile errors showing exactly which decoders needed updating. no silent failures. no runtime surprises.

**pattern matching changes how you think**

instead of defensive `if (data && data.results && data.results.length > 0)` checks everywhere, you model the states explicitly:
- `None` when there's no data
- `Some(data)` when there is

the compiler ensures you handle both cases. no forgotten null checks.

## the trade-off analysis

**what you gain:**
- **soundness** - if it compiles, types are guaranteed correct
- **refactoring confidence** - compiler guides you through changes
- **explicit error handling** - no forgotten null checks or error cases
- **immutability by default** - no accidental mutations

**what you pay:**
- **upfront type ceremony** - define types, write decoders, handle all cases
- **smaller ecosystem** - fewer libraries than typescript/javascript
- **build complexity** - opam + dune + webpack/bundler setup
- **team learning curve** - functional programming concepts aren't mainstream

## bottom line

analyzing this ocaml code shows functional programming isn't just academic theory. the type system, pattern matching, and explicit error handling eliminate entire classes of bugs. but they require upfront investment in types and decoders.

the code is longer and more explicit than equivalent typescript. but it's also more maintainable and correct by construction.

**live demo:** [options-max-pain.pages.dev](https://options-max-pain.pages.dev/)
