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
[Encoder Stack] → Encoded Representations
                              ↓
               [Decoder Stack] → Output Sequence
```

- The **Encoder** reads and understands the input.
- The **Decoder** generates the output, attending to both its own previous outputs and the encoder's representations.

Modern variants like **BERT** use only the encoder, while **GPT** uses only the decoder. But understanding the full encoder-decoder model reveals everything.

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

Here's a critical challenge: since the Transformer processes all tokens simultaneously (in parallel), it has **no inherent sense of order**. The word "dog bites man" and "man bites dog" would look identical without positional information.

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

**Why sinusoids?** They create unique patterns for each position, allow the model to generalize to sequence lengths not seen during training, and enable the model to learn relative positions (since `PE(pos+k)` can be expressed as a linear function of `PE(pos)`).

Modern models often use **learned positional embeddings** or more sophisticated schemes like **Rotary Position Embeddings (RoPE)** used in LLaMA and GPT-NeoX.

The final input to the encoder is:
```
Input = Token Embedding + Positional Encoding
```

---

## Step 3: The Attention Mechanism — The Heart of the Transformer

This is where the magic happens. Attention allows every token to directly "look at" every other token in the sequence and decide how much to focus on each one.

### Intuition
Consider the sentence: *"The animal didn't cross the street because **it** was too tired."*

What does "it" refer to — the animal or the street? Humans immediately know it's the animal. Attention lets the model make the same connection by having "it" attend strongly to "animal" and weakly to "street."

### Scaled Dot-Product Attention

Each token is transformed into three vectors through learned linear projections:
- **Query (Q)**: What this token is looking for
- **Key (K)**: What this token offers/advertises
- **Value (V)**: The actual content this token contributes

The attention formula is:

```
Attention(Q, K, V) = softmax(QK^T / √d_k) × V
```

Let's break this down step by step:

**1. Compute Similarity Scores (QK^T)**
The query of each token is dot-producted with the keys of all other tokens. A high dot product means "these two tokens are highly relevant to each other."

**2. Scale (÷ √d_k)**
Scores are divided by the square root of the key dimension. Without this scaling, dot products can grow very large for high-dimensional vectors, pushing the softmax into regions with extremely small gradients (the "vanishing gradient" problem during training).

**3. Softmax**
Scores are converted to probabilities (summing to 1) via softmax. These become **attention weights** — how much each token should attend to every other token.

**4. Weighted Sum of Values (× V)**
The attention weights are used to compute a weighted combination of Value vectors. Tokens with high attention weights contribute more to the output.

The result is a new representation for each token that incorporates contextual information from the entire sequence.

---

## Step 4: Multi-Head Attention

Running a single attention operation captures only one type of relationship. **Multi-Head Attention** runs several attention operations in parallel, each learning different relationship patterns.

```
MultiHead(Q, K, V) = Concat(head_1, ..., head_h) × W_O

where head_i = Attention(Q × W_Q_i, K × W_K_i, V × W_V_i)
```

Each "head" has its own learned projection matrices (W_Q, W_K, W_V), so they independently learn to attend to different aspects:
- One head might learn syntactic relationships (subject-verb agreement)
- Another might learn coreference (pronoun → noun)
- Another might learn positional proximity
- Another might capture semantic similarity

In the original paper, 8 heads were used with `d_k = d_model/h = 64` dimensions each. After parallel computation, all heads are concatenated and projected back to `d_model` dimensions.

This is analogous to how CNNs use multiple filters to detect different visual features simultaneously.

---

## Step 5: The Feed-Forward Network (FFN)

After attention, each token's representation passes through a **position-wise Feed-Forward Network** — applied independently and identically to each token:

```
FFN(x) = max(0, xW_1 + b_1) × W_2 + b_2
```

This is simply two linear transformations with a ReLU activation in between. The inner layer typically has 4× the dimension of the model (e.g., 2048 for a 512-dimensional model).

**Why is this needed?** Attention is fundamentally a weighted averaging operation — it's good at mixing information across positions but limited in its ability to transform individual token representations. The FFN provides the non-linear transformation capacity that gives the model expressive power to compute complex functions.

Think of it this way:
- **Attention** = communication between tokens (where to look)
- **FFN** = computation within each token (what to think)

---

## Step 6: Residual Connections and Layer Normalization

Two crucial engineering components wrap around each sub-layer (attention and FFN):

### Residual Connections
```
Output = LayerNorm(x + Sublayer(x))
```

The input `x` is added directly to the sublayer's output. This creates a "highway" for gradients to