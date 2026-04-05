# How Transformers Work in Deep Learning

## Introduction

The Transformer is one of the most revolutionary architectures in the history of deep learning. Introduced in the landmark 2017 paper **"Attention Is All You Need"** by Vaswani et al. at Google, it fundamentally changed how machines process sequential data — particularly language. Today, Transformers power virtually every state-of-the-art system in natural language processing (NLP), computer vision, protein folding, code generation, and beyond.

Unlike its predecessors (RNNs, LSTMs), the Transformer processes entire sequences simultaneously and relies entirely on a mechanism called **self-attention** to understand relationships between elements — no recurrence, no convolution required.

---

## The Core Problem Transformers Solve

Before Transformers, sequence modeling relied on **Recurrent Neural Networks (RNNs)** and **Long Short-Term Memory (LSTM)** networks. These models processed tokens one by one, left to right, maintaining a hidden state that carried information forward.

This design had critical limitations:

- **Sequential bottleneck**: Processing one token at a time made parallelization impossible.
- **Long-range dependency problem**: Information from early in a sequence often degraded or vanished by the time it was needed later — even with LSTMs.
- **Training speed**: Sequential computation made training on large datasets extremely slow.

The Transformer solved all three problems simultaneously.

---

## High-Level Architecture Overview

At its core, the original Transformer follows an **Encoder-Decoder** structure:

```
Input Sequence
      ↓
[Positional Encoding + Token Embeddings]
      ↓
┌─────────────────────┐
│    Encoder Stack     │  ← N identical layers
│  (Self-Attention +  │
│   Feed-Forward)     │
└─────────┬───────────┘
          │  Encoded Representations
          ↓
┌─────────────────────────────────────┐
│           Decoder Stack              │  ← N identical layers
│  Step 1: Masked Self-Attention       │  ← attends to previously
│          (on generated tokens)       │     generated tokens only
│  Step 2: Cross-Attention             │  ← attends to encoder output
│          (on encoder representations)│
│  Step 3: Feed-Forward                │
└─────────┬───────────────────────────┘
          │  One token generated per step
          ↓
    Output Sequence (built autoregressively)
```

- The **Encoder** reads the entire input sequence in parallel and produces a rich set of contextual representations.
- The **Decoder** generates the output sequence **one token at a time**. At each step, it attends to its own previously generated tokens (via masked self-attention) and to the encoder's representations (via cross-attention), then produces the next token. This process repeats until the sequence is complete.

### Why Encoder-Only or Decoder-Only?

Modern variants specialize this structure for their specific tasks. **BERT** uses only the encoder because tasks like classification and named entity recognition require understanding a complete input — there is no sequence to generate, so the decoder is unnecessary. **GPT** uses only the decoder because language generation is inherently autoregressive: the model produces one token at a time, conditioned on everything it has written before, with no separate input sequence to encode. Understanding the full encoder-decoder model reveals the design principles behind both of these specializations.

---

## Step 1: Tokenization and Input Embeddings

Before any computation, raw text must be converted to numbers.

### Tokenization
Text is split into **tokens** — which can be words, subwords, or characters. For example:
```
"Transformers are powerful" → ["Transform", "##ers", "are", "powerful"]
```
Each token is assigned an integer ID from a fixed vocabulary.

### Embedding Layer
Each token ID is mapped to a **dense vector** (typically 512 or 768 dimensions) via a learned embedding matrix. This converts discrete tokens into continuous representations that the model can compute with.

```
Token IDs → Embedding Matrix → Dense Vectors (d_model dimensions)
```

---

## Step 2: Positional Encoding

Here's a critical challenge: since the Transformer processes all tokens simultaneously (in parallel), it has **no inherent sense of order**. Without positional information, "dog bites man" and "man bites dog" would produce identical representations — a fatal flaw for language understanding.

To solve this, **positional encodings** are added to the token embeddings — vectors that encode each token's position in the sequence.

The original paper used fixed sinusoidal functions:

```
PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
```

Where:
- `pos` = position in the sequence
- `i` = dimension index
- `d_model` = embedding dimension

**Why sinusoids?** They produce a unique pattern for every position, and because `PE(pos+k)` can be expressed as a linear function of `PE(pos)`, the model can learn to reason about relative distances between tokens. The original paper also noted that sinusoidal encodings may help the model generalize to sequences longer than those seen during training, though this property is sensitive to implementation details and is not guaranteed in practice.

Modern models often use **learned positional embeddings** or more sophisticated schemes like **Rotary Position Embeddings (RoPE)**, used in LLaMA and GPT-NeoX, which encode relative positions directly into the attention computation rather than adding them to the input.

The final input to the encoder is:
```
Input = Token Embedding + Positional Encoding
```

---

## Step 3: The Attention Mechanism — The Heart of the Transformer

This is where the magic happens. Attention allows every token to directly "look at" every other token in the sequence and decide how much to focus on each one.

### Intuition
Consider the sentence: *"The animal didn't cross the street because **it** was too tired."*

What does "it" refer to — the animal or the street? Humans immediately know it's the animal. Attention lets the model make the same connection by having "it" attend strongly to "animal" and weakly to "street." This kind of long-range dependency resolution was precisely what RNNs struggled with.

### Scaled Dot-Product Attention

Each token is transformed into three vectors through learned linear projections:
- **Query (Q)**: What this token is looking for
- **Key (K)**: What this token offers or advertises
- **Value (V)**: The actual content this token contributes

The attention formula is:

```
Attention(Q, K, V) = softmax(QK^T / √d_k) × V
```

Let's break this down step by step:

**1. Compute Similarity Scores (QK^T)**
The query of each token is dot-producted with the keys of all other tokens. A high dot product means "these two tokens are highly relevant to each other."

**2. Scale (÷ √d_k)**
Scores are divided by the square root of the key dimension. Without this scaling, dot products can grow very large for high-dimensional vectors, pushing the softmax into regions where its output becomes nearly binary (one token gets all the attention, others get none) and gradients become vanishingly small — making the model extremely difficult to train.

**3. Softmax**
Scores are converted to probabilities that sum to 1 via softmax. These become **attention weights** — representing how much each token should attend to every other token.

**4. Weighted Sum of Values (× V)**
The attention weights are used to compute a weighted combination of Value vectors. Tokens with high attention weights contribute more to the output.

The result is a new representation for each token that incorporates contextual information from the entire sequence — a fundamentally richer representation than any fixed embedding could provide.

### A Concrete Numerical Example

To make this tangible, consider a 3-token sequence: **["cat", "sat", "mat"]**, processed through a single attention head with `d_k = 2` (a toy dimension for illustration).

Suppose after linear projection, the Query, Key, and Value matrices are:

```
       Q                K                V
cat: [1.0, 0.0]    cat: [1.0, 0.0]    cat: [1.