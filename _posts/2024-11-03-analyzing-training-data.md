---
layout: post
title: "Using Longest Increasing Subsequence to Analyze Training Block Effectiveness"
category: "Algorithms"
comments: true
---

When designing strength programs, we often organize training into 4-week blocks. By combining the Longest Increasing Subsequence (LIS) algorithm with training block analysis, we can identify which combinations of volume, intensity, and exercise variations lead to the best E1RM progressions.

## Understanding the Core Algorithm

First, let's look at the elegant algorithm that powers our analysis - the LIS implementation using Patience Sorting:

```elixir
def find_progression(nums, min_improvement \\ 2.5) do
  # dp[i] stores smallest number that can end subsequence of length i+1
  dp = []
  prev = %{}  # For reconstructing the sequence

  {dp, prev} = Enum.with_index(nums)
    |> Enum.reduce({dp, prev}, fn {num, i}, {dp, prev} ->
      # Find position where this number belongs
      pos = find_position(dp, num, min_improvement)

      # Track for reconstruction
      prev = if pos > 0,
        do: Map.put(prev, i, {pos - 1, Enum.at(dp, pos - 1)}),
        else: prev

      # Update dp array
      dp = if pos == length(dp),
        do: dp ++ [num],
        else: List.replace_at(dp, pos, num)

      {dp, prev}
    end)

  # Reconstruct the sequence
  {length(dp), reconstruct(nums, prev, length(dp) - 1, dp)}
end

defp find_position(dp, target, min_improvement) do
  do_binary_search(dp, target, min_improvement, 0, length(dp))
end

defp do_binary_search(dp, target, min_improvement, left, right) when left < right do
  mid = div(left + right, 2)
  mid_val = Enum.at(dp, mid)

  cond do
    mid_val == nil -> left
    target - mid_val >= min_improvement ->
      do_binary_search(dp, target, min_improvement, mid + 1, right)
    true ->
      do_binary_search(dp, target, min_improvement, left, mid)
  end
end
defp do_binary_search(_, _, _, left, _), do: left
```

This algorithm finds the longest sequence of E1RMs where each value is at least `min_improvement` greater than the previous. Time complexity is O(n log n).

## Structuring Training Data

```elixir
defmodule TrainingBlock do
  defstruct [
    :block_number,
    :start_date,
    :end_date,
    :primary_movement,     # e.g., "Comp Squat", "Paused Bench"
    :volume_per_session,   # sets * reps
    :intensity_range,      # % of E1RM
    :frequency_per_week,
    :variations_used,      # e.g., ["Paused", "Tempo", "Close Grip"]
    :sets,                 # List of actual training sets
    :starting_e1rm,
    :ending_e1rm
  ]
end

defmodule TrainingSet do
  defstruct [:date, :weight, :reps, :rpe, :e1rm]

  def calculate_e1rm(weight, reps) do
    weight * (36 / (37 - reps))  # Brzycki formula
  end
end
```

## Block Analysis System

```elixir
defmodule BlockAnalyzer do
  def analyze_progression_patterns(blocks, min_improvement \\ 2.5) do
    # Group blocks by exercise
    blocks_by_exercise = Enum.group_by(blocks, & &1.primary_movement)

    # Analyze each exercise
    Enum.map(blocks_by_exercise, fn {exercise, exercise_blocks} ->
      # Get E1RMs
      e1rms = Enum.map(exercise_blocks, & &1.ending_e1rm)

      # Find progression using LIS
      {length, progression} = find_progression(e1rms, min_improvement)

      # Map back to block characteristics
      successful_blocks =
        exercise_blocks
        |> Enum.filter(& &1.ending_e1rm in progression)
        |> Enum.sort_by(& &1.block_number)

      {exercise, analyze_characteristics(successful_blocks)}
    end)
  end

  defp analyze_characteristics(blocks) do
    %{
      avg_volume_per_session: average_volume(blocks),
      most_successful_intensity: common_intensity_range(blocks),
      optimal_frequency: most_common_frequency(blocks),
      effective_variations: most_effective_variations(blocks),
      block_sequence: extract_block_sequence(blocks)
    }
  end
end
```

## Example Usage and Output

Here's how we can analyze 6 months (6 blocks) of training:

```elixir
blocks = [
  %TrainingBlock{
    block_number: 1,
    primary_movement: "Competition Bench",
    volume_per_session: 15,  # 5 sets of 3
    intensity_range: "80-85%",
    frequency_per_week: 2,
    variations_used: ["Paused"],
    starting_e1rm: 100,
    ending_e1rm: 102.5
  },
  %TrainingBlock{
    block_number: 2,
    primary_movement: "Competition Bench",
    volume_per_session: 24,  # 6 sets of 4
    intensity_range: "75-80%",
    frequency_per_week: 2,
    variations_used: ["Paused", "Tempo"],
    starting_e1rm: 102.5,
    ending_e1rm: 105
  },
  # ... more blocks ...
]

analysis = BlockAnalyzer.analyze_progression_patterns(blocks)
```

The output shows us the successful progression patterns:

```elixir
%{
  "Competition Bench" => %{
    progression: [102.5, 105.0, 108.5, 112.0],
    characteristics: %{
      avg_volume_per_session: 20,
      most_successful_intensity: "75-80%",
      optimal_frequency: 2,
      effective_variations: ["Paused", "Tempo"],
      block_sequence: [
        %{volume: "moderate", intensity: "moderate"},
        %{volume: "high", intensity: "moderate"},
        %{volume: "moderate", intensity: "high"},
        %{volume: "low", intensity: "very high"}
      ]
    }
  }
}
```

## How It Works

1. **Finding True Progression**
   ```elixir
   # Example E1RMs: [100, 102.5, 101, 105, 104, 108]
   # With min_improvement = 2.5kg:

   Step 1: [100]
   Step 2: [100, 102.5]
   Step 3: [100, 101]       # Replace 102.5 with 101
   Step 4: [100, 101, 105]  # New pile (>2.5kg improvement)
   Step 5: [100, 101, 104]  # Replace 105 with 104
   Step 6: [100, 101, 104, 108]  # New pile

   # Result: [100, 101, 104, 108] - Four block progression
   ```

2. **Block Pattern Analysis**
   - Each number in our progression represents a successful block
   - We analyze characteristics of these blocks
   - Look for patterns in volume, intensity, and variation

## Using the Results

1. **Program Design**
   ```elixir
   def design_next_block(current_e1rm, analysis_results) do
    successful_pattern = find_matching_pattern(analysis_results)
    next_block_characteristics = predict_next_block(successful_pattern)

    %{
      suggested_volume: next_block_characteristics.volume,
      suggested_intensity: next_block_characteristics.intensity,
      suggested_variations: next_block_characteristics.variations,
      expected_improvement: next_block_characteristics.expected_gain
    }
   end
   ```

2. **Progress Prediction**
   ```elixir
   def predict_block_outcome(current_e1rm, block_characteristics) do
    similar_blocks = find_similar_blocks(block_characteristics)
    average_improvement = calculate_avg_improvement(similar_blocks)

    %{
      expected_improvement: average_improvement,
      confidence: calculate_confidence(similar_blocks),
      recommended_modifications: suggest_modifications(similar_blocks)
    }
   end
   ```

## Conclusion

By using the LIS algorithm with Patience Sorting, we can:
1. Find genuine progression patterns in our training
2. Identify block characteristics that lead to consistent progress
3. Make data-driven decisions about program design
4. Predict likely outcomes of different block structures

The algorithm's efficiency (O(n log n)) makes it practical for analyzing large training histories, while its ability to find strictly increasing sequences with minimum improvements makes it perfect for strength training analysis.

---
