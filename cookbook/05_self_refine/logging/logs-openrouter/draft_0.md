# How Transformers Work in Deep Learning

## Introduction

The Transformer is one of the most revolutionary architectures in modern deep learning, introduced in the landmark 2017 paper **"Attention Is All You Need"** by Vaswani et al. at Google. Before Transformers, sequential tasks like language translation and text generation were dominated by Recurrent Neural Networks (RNNs) and LSTMs, which processed data one token at a time. Transformers broke this bottleneck by processing entire sequences in parallel, enabling unprecedented scale and performance.

Today, Transformers are the backbone of models like **GPT-4, BERT, T5, DALL-E, Whisper**, and virtually every state-of-the-art AI system.

---

## The Core Problem Transformers Solve

Before understanding how Transformers work, it helps to understand what they replaced and why.

### Limitations of RNNs
- **Sequential processing**: RNNs process tokens one at a time, making them slow to train.
- **Vanishing gradients**: Information from early tokens gets "forgotten" as sequences grow longer.
- **Limited parallelism**: Dependencies between time steps prevent efficient GPU utilization.

Transformers solve all three problems by replacing recurrence with a mechanism called **self-attention**, allowing every token to directly interact with every other token simultaneously.

---

## High-Level Architecture

A standard Transformer has two main components:

```
Input Sequence
      ↓
[Encoder Stack]  →  Encoded Representations
                            ↓
[Decoder Stack]  →  Output Sequence
```

- The **Encoder** reads and understands the input.
- The **Decoder** generates the output, one token at a time, using the encoder's representations.

For tasks like classification or embeddings (e.g., BERT), only the encoder is used. For generation tasks (e.g., GPT), only the decoder is used. For sequence-to-sequence tasks like translation (e.g., T5), both are used.

---

## Step-by-Step: How a Transformer Processes Data

### Step 1: Tokenization and Embedding

Before entering the Transformer, raw text is broken into **tokens** (words, subwords, or characters) and converted into numerical vectors.

```
"The cat sat" → ["The", "cat", "sat"] → [token IDs] → [embedding vectors]
```

Each token is mapped to a dense vector of dimension **d_model** (e.g., 512 or 768). These embeddings are learned during training and capture semantic meaning.

---

### Step 2: Positional Encoding

Unlike RNNs, Transformers have no inherent sense of order. To inject position information, **positional encodings** are added to the embeddings.

The original paper used sinusoidal functions:

```
PE(pos, 2i)   = sin(pos / 10000^(2i / d_model))
PE(pos, 2i+1) = cos(pos / 10000^(2i / d_model))
```

This gives each position a unique signature that the model can learn to interpret. Modern models often use **learned positional embeddings** or more advanced schemes like **Rotary Position Embeddings (RoPE)** used in LLaMA and GPT-NeoX.

The result:
```
Input to Transformer = Token Embedding + Positional Encoding
```

---

### Step 3: The Self-Attention Mechanism

This is the heart of the Transformer. Self-attention allows every token to look at every other token and decide how much to "attend" to each one when building its representation.

#### Queries, Keys, and Values

For each token, three vectors are computed using learned weight matrices:

| Vector | Symbol | Role |
|--------|--------|------|
| **Query** | Q | "What am I looking for?" |
| **Key** | K | "What do I contain?" |
| **Value** | V | "What information do I carry?" |

```
Q = X · W_Q
K = X · W_K
V = X · W_V
```

Where **X** is the input matrix and **W_Q, W_K, W_V** are learned weight matrices.

#### Computing Attention Scores

The attention score between two tokens is computed as the dot product of their Query and Key vectors:

```
Attention(Q, K, V) = softmax( QK^T / √d_k ) · V
```

Breaking this down:
1. **QK^T** — Dot product of all queries with all keys → produces a score matrix showing how relevant each token is to every other token.
2. **÷ √d_k** — Scaling by the square root of key dimension to prevent gradients from vanishing in high dimensions.
3. **softmax(...)** — Normalizes scores into probabilities (attention weights that sum to 1).
4. **× V** — Weighted sum of value vectors → the final attended representation.

#### Intuitive Example

Consider the sentence: *"The animal didn't cross the street because **it** was too tired."*

What does "it" refer to? "animal" or "street"? Self-attention allows the model to compute high attention weights between "it" and "animal," resolving the coreference correctly.

---

### Step 4: Multi-Head Attention

Instead of computing attention once, Transformers run **h parallel attention heads**, each with its own Q, K, V projections.

```
MultiHead(Q, K, V) = Concat(head_1, ..., head_h) · W_O

where head_i = Attention(Q·W_Qi, K·W_Ki, V·W_Vi)
```

**Why multiple heads?**
- Different heads can attend to different aspects simultaneously.
- One head might capture syntactic relationships (subject-verb agreement).
- Another might capture semantic relationships (word meaning).
- Another might focus on positional proximity.

This gives the model a rich, multi-perspective understanding of context.

---

### Step 5: Add & Norm (Residual Connections + Layer Normalization)

After each sub-layer (attention or feed-forward), two operations are applied:

```
Output = LayerNorm(x + SubLayer(x))
```

1. **Residual Connection (x + SubLayer(x))**: Adds the original input back to the output. This prevents vanishing gradients and allows information to flow directly through the network.

2. **Layer Normalization**: Normalizes the values across the feature dimension, stabilizing training and accelerating convergence.

---

### Step 6: Feed-Forward Network (FFN)

After multi-head attention, each token's representation passes through a **position-wise feed-forward network** — a small two-layer MLP applied independently to each token:

```
FFN(x) = max(0, x·W_1 + b_1) · W_2 + b_2
```

- Typically, the inner dimension is 4× larger than d_model (e.g., 2048 if d_model = 512).
- Uses **ReLU** or **GELU** activation.
- This layer allows the model to apply non-linear transformations and "think" about each token's representation after attending to context.

The FFN is where much of the model's **factual knowledge** is thought to be stored.

---

### Step 7: Stacking Encoder Layers

The encoder consists of **N identical layers** (typically 6–96 depending on model size), each containing:

```
[Multi-Head Self-Attention] → [Add & Norm] → [Feed-Forward Network] → [Add & Norm]
```

As data flows through each layer, representations become increasingly abstract and contextual. Early layers capture syntax; deeper layers capture semantics and world knowledge.

---

### Step 8: The Decoder

The decoder is similar to the encoder but has **three sub-layers** per block:

#### 1. Masked Self-Attention
The decoder attends to previously generated tokens. The "masking" prevents the model from looking at future tokens (causal masking), ensuring autoregressive generation:

```
Token 1 can only see: [Token 1]
Token 2 can only see: [Token 1, Token 2]
Token 3 can only see: [Token 1, Token 2, Token 3]
```

#### 2. Cross-Attention (Encoder-Decoder Attention)
The decoder attends to the encoder's output. Here: