# How Transformers Work in Deep Learning

## Introduction

The Transformer is one of the most influential architectures in modern deep learning, introduced in the landmark 2017 paper **"Attention Is All You Need"** by Vaswani et al. at Google. Before Transformers, sequence modeling relied heavily on recurrent neural networks (RNNs) and LSTMs, which processed data sequentially — one token at a time. Transformers discarded recurrence entirely and replaced it with a mechanism called **self-attention**, enabling massive parallelization and far superior performance on tasks involving language, images, audio, and more.

This document provides a comprehensive, step-by-step explanation of how Transformers work.

---

## The Core Problem Transformers Solve

Consider translating the sentence:

> *"The animal didn't cross the street because **it** was too tired."*

What does "it" refer to — the animal or the street? Humans resolve this through **context**: we look at all the words in the sentence simultaneously and reason about relationships. Traditional RNNs struggled with this because they passed information through a sequential hidden state, causing distant dependencies to fade (the vanishing gradient problem).

Transformers solve this by allowing every word to **directly attend to every other word** in a single operation, regardless of distance.

---

## High-Level Architecture Overview

A standard Transformer consists of two main blocks:

```
Input Sequence
      ↓
[Encoder Stack]  ← Understands the input
      ↓
[Decoder Stack]  ← Generates the output
      ↓
Output Sequence
```

Each **Encoder** and **Decoder** is a stack of identical layers (typically 6–12 in the original paper, up to 96+ in large models like GPT-4).

> **Note:** Not all Transformers use both components. BERT uses only the Encoder; GPT uses only the Decoder.

---

## Step 1: Tokenization and Embeddings

Before any computation, raw text must be converted into numbers.

### Tokenization
Text is split into **tokens** — which may be words, subwords, or characters depending on the tokenizer.

```
"Hello, world!" → ["Hello", ",", "world", "!"]
```

Each token is mapped to a unique integer ID from a vocabulary.

### Token Embeddings
Each token ID is converted into a **dense vector** of real numbers (e.g., 512 dimensions). These embeddings are learned during training.

```
"Hello" → [0.23, -0.45, 0.87, ..., 0.12]  (512 numbers)
```

These vectors capture semantic meaning — words with similar meanings cluster together in embedding space.

---

## Step 2: Positional Encoding

Unlike RNNs, Transformers process all tokens **simultaneously**, so they have no built-in notion of order. To inject positional information, a **positional encoding** is added to each token embedding.

The original paper used fixed sinusoidal functions, where **even dimensions use sine and odd dimensions use cosine**:

$$PE_{(pos, 2i)} = \sin\left(\frac{pos}{10000^{2i/d_{model}}}\right)$$

$$PE_{(pos, 2i+1)} = \cos\left(\frac{pos}{10000^{2i/d_{model}}}\right)$$

Where:
- `pos` = position of the token in the sequence
- `i` = dimension index
- `d_model` = embedding dimension

**Why sinusoids?** They produce unique patterns for each position, and the model can learn relative positions because `PE(pos + k)` can be expressed as a linear function of `PE(pos)`. This means the model can generalize to sequence lengths not seen during training.

Modern models often replace fixed sinusoidal encodings with **learned positional embeddings** (used in BERT) or more advanced schemes. One prominent example is **Rotary Position Embedding (RoPE)**, used in LLaMA and many recent models, which encodes relative distances between tokens directly into the attention computation rather than adding a fixed vector to each token. This makes it easier for the model to generalize to longer sequences than it saw during training.

> **Advanced note:** RoPE works by applying rotation matrices to Query and Key vectors before computing attention scores, so the dot product between any two tokens naturally reflects how far apart they are rather than where each sits in absolute terms. See the original RoPE paper (Su et al., 2021) for a full treatment.

The final input representation is:

```
Input = Token Embedding + Positional Encoding
```

---

## Step 3: The Encoder

The encoder transforms the input sequence into a rich contextual representation. It consists of **N identical layers**, each containing two sub-layers:

1. **Multi-Head Self-Attention**
2. **Position-wise Feed-Forward Network**

Each sub-layer wraps its computation in a **residual connection** followed by **layer normalization**:

```
Output = LayerNorm(x + SubLayer(x))
```

**Residual connections** serve two purposes: they allow gradients to flow directly backward through the network during training, which enables very deep Transformers (100+ layers) to train without vanishing gradients, and they allow each layer's input to propagate forward unchanged, so useful features are never bottlenecked through a nonlinearity. **Layer normalization** stabilizes the scale of activations across the feature dimension, allowing higher learning rates and more consistent training. Both are introduced here because every sub-layer in the encoder and decoder uses this same pattern.

### 3.1 Self-Attention: The Heart of the Transformer

Self-attention allows each token to "look at" all other tokens and decide which ones are most relevant.

#### The Query, Key, Value Framework

For each token, three vectors are computed:

| Vector | Role | Analogy |
|--------|------|---------|
| **Query (Q)** | What am I looking for? | A search query |
| **Key (K)** | What do I represent? | A document tag |
| **Value (V)** | What information do I carry? | The document content |

These are computed by multiplying the input by learned weight matrices:

```
Q = X · W_Q
K = X · W_K
V = X · W_V
```

#### Computing Attention Scores

The attention score between two tokens is computed as the **dot product** of their Query and Key vectors:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

**Breaking this down:**

1. **`QK^T`** — Compute similarity between every pair of tokens. A higher dot product means the two tokens are more relevant to each other.
2. **`/ √d_k`** — Scale by the square root of the key dimension. Without this scaling, the variance of dot products grows as O(d_k), causing softmax outputs to concentrate nearly all probability mass on a single token and leaving the others with vanishing gradients. Dividing by `√d_k` brings the variance back to O(1), keeping softmax sensitive across all tokens and allowing gradients to flow cleanly.
3. **`softmax(...)`** — Convert scores to probabilities that sum to 1. This is the **attention weight**.
4. **`× V`** — Weighted sum of Value vectors. Tokens with high attention weights contribute more to the output.

**Concrete Example:**

For the sentence *"The cat sat on the mat"*, the attention matrix might look like:

```
         The   cat   sat    on   the   mat   | Sum
The    [ 0.60, 0.20, 0.05, 0.05, 0.05, 0.05 ] = 1.0
cat    [ 0.10, 0.50, 0.20, 0.05, 0.05, 0.10 ] = 1.0
sat    [ 0.05, 0.30, 0.40, 0.10, 0.05, 0.10 ] = 1.0
```

> **Note:** These values are illustrative. Real attention patterns — particularly in early layers — are often far noisier and less interpretable than this example suggests. Actual weights depend on the model's learned weight matrices and the specific input embeddings, and do not always align neatly with human-readable linguistic relationships.

Each row sums to 1. In this idealized example, "sat" attends strongly to "cat", reflecting a subject-verb relationship.

### 3.2 Multi-Head Attention

A single attention operation captures one type of relationship. **Multi-head attention** runs several attention operations in parallel, each with different learned weight matrices:

```
head_i = Attention(Q·W_Q_i, K·W_K_i, V·W_V_i)

MultiHead(Q, K, V) = Concat(head_1, ..., head_h) · W_O
```

**Why multiple heads?**

Different heads learn to attend to different types of relationships simultaneously:
- Head 1 might track **syntactic dependencies** (subject → verb)
- Head 2 might track **coreference** (pronoun → noun)
- Head 3 might track **positional proximity**

The original paper used **8 heads** with `d_k = 64` (total dimension = 512).

### 3.3 Feed-Forward Network

After attention, each token's representation is passed through a **position-wise feed-forward network** — the same network applied independently to each token:

```
FFN(x) = max(0, x·W₁ + b₁)·W₂ + b₂
```

This is two linear layers with a ReLU activation in between. The inner dimension is typically 4× the model dimension (e.g., 2048 for a 512-dim model).

**Role:** While attention mixes information *across* tokens, the FFN processes each token's representation *independently*, applying learned non-linear transformations that enable the model to compute complex functions of each token's representation.

### 3.4 Computational Complexity: The O(n²) Bottleneck

Self-attention computes a score between **every pair of tokens**, so its cost scales as **O(n²)** in sequence length, where n is the number of tokens. For short sequences this is negligible, but at n = 10,000 tokens the attention matrix alone contains 100 million entries — making standard attention prohibitively slow and memory-intensive for long documents, codebases, or high-resolution images.

This is an active area of research. Proposed solutions include:
- **Sliding window attention** (Longformer): each token attends only to a local window of neighbors, reducing complexity to O(n).
- **Linear attention** variants: approximate the full attention matrix using kernel methods, achieving O(n) complexity with some accuracy trade-off.
- **Flash Attention**: does not reduce theoretical complexity but dramatically reduces memory usage by computing attention in tiled blocks, making standard attention practical at much longer sequence lengths.

---

## Step 4: The Decoder

The decoder generates the output sequence **one token at a time**, using two sources of information:

1. **The tokens it has already generated** (autoregressive)
2. **The encoder's output** (cross-attention)

Each decoder layer has **three sub-layers**:

1. **Masked Multi-Head Self-Attention**
2. **Multi-Head Cross-Attention**
3. **Feed-Forward Network**

> **Decoder-only models** (like GPT) omit cross-attention and the encoder entirely. Because language modeling is inherently autoregressive — each token is predicted from the tokens before it — no separate encoder is needed to process a distinct input modality, making the architecture simpler and more parameter-efficient for this task.

### 4.1 Masked Self-Attention

When generating the token at position `t`, the decoder should only attend to positions `1` through `t` — not future positions, which haven't been generated yet. This is enforced by **causal masking**: future attention scores are set to `-∞` before softmax, so they become exactly 0 after softmax.

```
Mask:
Position:  1    2    3    4
Token 1: [✓,   ✗,   ✗,   ✗]
Token 2: [✓,   ✓,   ✗,   ✗]
Token 3: [✓,   ✓,   ✓,   ✗]
Token 4: [✓,   ✓,   ✓,   ✓]
```

This causal masking is what