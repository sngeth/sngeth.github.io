---
layout: post
title: "Why Does AI Like to 'Delve' So Much?"
category: "AI"
comments: true
---
---

If you've interacted with an AI language model, you've probably noticed that certain words or phrases tend to come up again and again. One word that often appears is "delve" — as in "let's delve into this topic." But why does AI "like" to use certain words so much? The answer lies in how these models generate text and, more specifically, in the processes known as **greedy decoding** and **stochastic sampling**.

---

## The Basics of AI Text Generation

AI language models, like GPT, generate text by predicting the next word in a sequence based on previous words. The goal is to model the probability of the next word given the context. Formally, this looks something like this:

```
P(x_t | x_1, x_2, ..., x_t-1)
```

In plain terms, the model predicts the probability of the next word (`x_t`) based on all the words that came before it (`x_1, x_2, ..., x_t-1`). To actually generate text, we need a strategy for choosing the next word. This is where **greedy decoding** and **stochastic sampling** come into play.

### Greedy Decoding

In **greedy decoding**, the model always picks the word with the highest probability at each step. This results in a very focused and deterministic sequence of text. While this can be useful for ensuring coherence, it tends to make the output repetitive or overly cautious — which explains why certain phrases like "delve" might get overused.

Here's an Elixir example of greedy decoding:

```elixir
defmodule GreedyDecoder do
  def predict_next_word(tokens, model) do
    tokens
    |> Enum.map(&model.(&1))
    |> Enum.max_by(fn {_, probability} -> probability end)
    |> elem(0)
  end
end

# Example usage
vocab = ["explore", "delve", "analyze", "investigate"]
model = fn token -> Enum.zip(vocab, [0.6, 0.3, 0.05, 0.05]) end
tokens = ["The", "researcher", "decided", "to"]

GreedyDecoder.predict_next_word(tokens, model)
# Output: "explore"
```

In this case, the word with the highest probability ("explore") is always selected. If "delve" has a consistently high probability in similar contexts, you'll see it again and again.

### Stochastic Sampling

**Stochastic sampling**, on the other hand, introduces some randomness. Instead of always picking the word with the highest probability, the model samples from the probability distribution — meaning that words with lower probabilities still have a chance to be chosen. This method encourages more variety and creativity in the generated text.

Here’s how you could implement stochastic sampling in Elixir:

```elixir
defmodule StochasticDecoder do
  def predict_next_word(tokens, model) do
    tokens
    |> Enum.map(&model.(&1))
    |> Enum.reduce([], fn {word, prob}, acc -> acc ++ List.duplicate(word, round(prob * 100)) end)
    |> Enum.shuffle()
    |> List.first()
  end
end

# Example usage
vocab = ["explore", "delve", "analyze", "investigate"]
model = fn token -> Enum.zip(vocab, [0.6, 0.3, 0.05, 0.05]) end
tokens = ["The", "researcher", "decided", "to"]

StochasticDecoder.predict_next_word(tokens, model)
# Possible outputs: "delve", "explore", "investigate", or "analyze" (depending on the random sampling)
```

By using stochastic sampling, there's a chance the AI will pick words other than "explore", even though it has the highest probability. This can lead to more diverse and creative outputs.

---

## How to Adjust the "Temperature" for More Creative Output

If you want the AI to generate more creative and varied responses, one of the most important parameters to adjust is the **temperature**.

- **Lower temperatures** (closer to 0) make the model more deterministic, meaning it will stick to the most probable word choices.
- **Higher temperatures** (closer to 1) introduce more randomness, encouraging the model to pick less common words and be more inventive.

### How to Change the Temperature

In practice, changing the temperature depends on the tool or platform you're using:

- **OpenAI API**: You can set the `temperature` parameter when making API calls. For example, in OpenAI’s API:
  ```json
  {
    "model": "gpt-4",
    "prompt": "The researcher decided to",
    "temperature": 0.8
  }
  ```

- **Playground**: If you're using OpenAI's **Playground**, you can adjust the temperature with a slider before generating text.

- **Other apps and services**: Many tools and platforms that use AI allow you to adjust the creativity or style of the generated text. These usually map to the temperature setting internally.

Here’s an example showing how to adjust the temperature in Elixir:

```elixir
defmodule TemperatureDecoder do
  def predict_next_word(tokens, model, temperature \\ 1.0) do
    tokens
    |> Enum.map(&model.(&1))
    |> Enum.map(fn {word, prob} -> {word, :math.pow(prob, 1.0 / temperature)} end)
    |> Enum.reduce([], fn {word, prob}, acc -> acc ++ List.duplicate(word, round(prob * 100)) end)
    |> Enum.shuffle()
    |> List.first()
  end
end

# Example usage with temperature
vocab = ["explore", "delve", "analyze", "investigate"]
model = fn token -> Enum.zip(vocab, [0.6, 0.3, 0.05, 0.05]) end
tokens = ["The", "researcher", "decided", "to"]

TemperatureDecoder.predict_next_word(tokens, model, 0.7)
# Output will vary based on the adjusted temperature
```

Lowering the temperature parameter leads to more predictable outcomes, while raising it adds creativity and variety to the AI's word choices.

---

## Conclusion

AI language models generate text by predicting the next word based on prior context. Techniques like **greedy decoding** result in more deterministic, focused text, while **stochastic sampling** can add variety and creativity. If you're looking to guide the AI towards more varied, creative outputs, adjusting the **temperature** is key. Lower temperatures make responses more predictable, while higher temperatures foster creativity by allowing more diverse word choices.

So, why does AI like to "delve" so much? It’s not that the model has a preference, but rather that certain words come up more often in certain contexts due to how probabilities are calculated. By understanding and tweaking decoding strategies, you can have more control over the AI's output — and maybe even get it to "explore" a little more often than "delve."

---
