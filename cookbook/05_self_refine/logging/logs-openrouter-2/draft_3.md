# How Transformers Work in Deep Learning

## Introduction

The Transformer is one of the most revolutionary architectures in the history of deep learning. Introduced in the landmark 2017 paper **"Attention Is All You Need"** by Vaswani et al. at Google, it fundamentally changed how machines process sequential data — particularly language. Today, Transformers power virtually every state-of-the-art system in natural language processing (NLP), computer vision, protein folding, code generation, and beyond.

Unlike its predecessors (RNNs, LSTMs), the Transformer processes entire sequences simultaneously and relies entirely on a mechanism called **self-attention** to understand relationships between elements — no recurrence, no convolution required.

---

## The Core Problem Transformers Solve

Before Transformers, sequence modeling relied on **Recurrent Neural Networks (RNNs)** and **Long Short-Term Memory (LSTM)** networks. These models processed tokens one by one, left to right, maintaining a hidden state that carried information forward.

This design had critical limitations:

- **Sequential bottleneck**: Processing one token at a time made parallelization impossible during training.
- **Long-range dependency problem**: Information from early in a sequence often degraded or vanished by the time it was needed later — even with LSTMs.
- **Training speed**: Sequential computation made training on large datasets extremely slow.

The Transformer solved all three problems simultaneously — though, as we will see, not without introducing its own trade-offs.

---

## High-Level Architecture Overview

At its core, the original Transformer follows an **Encoder-Decoder** structure:

```
Input Sequence
      ↓
[Positional Encoding + Token Embeddings]
      ↓
┌──────────────────────────────────────┐
│             Encoder Stack             │  ← N identical layers
│                                       │
│  ┌─────────────────────────────────┐  │
│  │     Multi-Head Self-Attention   │  │
│  └────────────────┬────────────────┘  │
│                   │ + residual        │
│  ┌────────────────▼────────────────┐  │
│  │         Layer Norm              │  │
│  └────────────────┬────────────────┘  │
│                   │                   │
│  ┌────────────────▼────────────────┐  │
│  │      Feed-Forward Network       │  │
│  └────────────────┬────────────────┘  │
│                   │ + residual        │
│  ┌────────────────▼────────────────┐  │
│  │         Layer Norm              │  │
│  └─────────────────────────────────┘  │
└──────────────────┬───────────────────┘
                   │  Encoded Representations
                   ↓
┌──────────────────────────────────────────────┐
│                Decoder Stack                  │  ← N identical layers
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │    Masked Multi-Head Self-Attention      │  │  ← attends to previously
│  │        (on generated tokens)            │  │     generated tokens only
│  └──────────────────┬──────────────────────┘  │
│                     │ + residual              │
│  ┌──────────────────▼──────────────────────┐  │
│  │             Layer Norm                  │  │
│  └──────────────────┬──────────────────────┘  │
│                     │                         │
│  ┌──────────────────▼──────────────────────┐  │
│  │  Cross-Attention (on encoder output)    │  │  ← attends to encoder
│  └──────────────────┬──────────────────────┘  │     representations
│                     │ + residual              │
│  ┌──────────────────▼──────────────────────┐  │
│  │             Layer Norm                  │  │
│  └──────────────────┬──────────────────────┘  │
│                     │                         │
│  ┌──────────────────▼──────────────────────┐  │
│  │         Feed-Forward Network            │  │
│  └──────────────────┬──────────────────────┘  │
│                     │ + residual              │
│  ┌──────────────────▼──────────────────────┐  │
│  │             Layer Norm                  │  │
│  └─────────────────────────────────────────┘  │
└──────────────────────┬───────────────────────┘
                       │
                       ↓
              Linear Projection
                       ↓
              Softmax over Vocabulary
                       ↓
          Probability Distribution → Next Token
                       ↓
         Output Sequence (built autoregressively)
```

- The **Encoder** reads the entire input sequence in parallel and produces a rich set of contextual representations.
- The **Decoder** generates the output sequence **one token at a time**. At each step, it attends to its own previously generated tokens (via masked self-attention) and to the encoder's representations (via cross-attention), then produces the next token. This process repeats until the sequence is complete.

### From Decoder Output to Token Probabilities

After the final decoder layer, the model must convert a continuous vector into an actual token prediction. This happens in two steps:

1. **Linear projection**: The decoder's output vector (of dimension `d_model`) is projected to a vector of size `V`, where `V` is the vocabulary size — typically 30,000 to 100,000 tokens. Each entry in this vector is an unnormalized score (logit) for the corresponding token.

2. **Softmax**: The logits are passed through a softmax function, converting them into a probability distribution over the entire vocabulary. The token with the highest probability is selected as the next output (a strategy called **greedy decoding**), though more sophisticated strategies like **beam search** or **nucleus sampling** are often used in practice.

During **training**, the model receives the correct output sequence shifted by one position (teacher forcing), and the loss is computed across all positions simultaneously — making training fully parallel. During **inference**, the model has no ground truth to reference; it feeds its own previous predictions back as input, generating one token at a time until it produces a special end-of-sequence token.

### Why Encoder-Only or Decoder-Only?

Modern variants specialize the full structure for specific tasks. **BERT** uses only the encoder because tasks like classification and named entity recognition require understanding a complete input — there is no sequence to generate, so the decoder is unnecessary. **GPT** uses only the decoder because language generation is inherently autoregressive: the model produces one token at a time, conditioned on everything it has written before, with no separate input sequence to encode. Understanding the full encoder-decoder model reveals the design principles behind both of these specializations.

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

Here is a critical challenge: since the Transformer processes all tokens simultaneously (in parallel), it has **no inherent sense of order**. Without positional information, "dog bites man" and "man bites dog" would produce identical representations — a fatal flaw for language understanding.

To solve this, **positional encodings** are added to the token embeddings — vectors that encode each token's position in the sequence.

The original paper used fixed sinusoidal functions:

```