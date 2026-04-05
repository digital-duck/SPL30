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

**Why sinusoids?** They produce unique patterns for each position, and the model can learn relative positions because `PE(pos + k)` can be expressed as a linear function of `PE(pos)`. This property is important for implementors: it means the model can generalize to sequence lengths not seen during training.

Modern models often use learned positional embeddings (BERT) or more advanced schemes like **Rotary Position Embedding (RoPE)**, used in LLaMA, which encodes position directly into the attention computation rather than adding it to the embeddings — making it better suited to long sequences and more naturally capturing relative distances between tokens.

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

Residual connections allow gradients to flow directly backward through the network during training, which is what enables very deep Transformers (100+ layers) to train without vanishing gradients. Layer normalization stabilizes the scale of activations across the feature dimension, allowing higher learning rates and more consistent training. Both are introduced here because every sub-layer in the encoder and decoder uses this same pattern.

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
2. **`/ √d_k`** — Scale by the square root of the key dimension. Without this scaling, large dot products push the softmax function into regions where one token receives nearly all the probability mass and the rest receive almost none. In this saturated regime, gradients become vanishingly small, stalling learning. Dividing by `√d_k` keeps the dot products in a range where softmax remains sensitive and gradients flow cleanly.
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

Each row sums to 1. The word "sat" attends strongly to "cat" (subject-verb relationship), reflecting that the model has learned to connect verbs with their subjects.

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

**Role:** While attention mixes information *across* tokens, the FFN processes each token's representation *independently*, acting as a per-token transformation that stores factual knowledge.

---

## Step 4: The Decoder

The decoder generates the output sequence **one token at a time**, using two sources of information:

1. **The tokens it has already generated** (autoregressive)
2. **The encoder's output** (cross-attention)

Each decoder layer has **three sub-layers**:

1. **Masked Multi-Head Self-Attention**
2. **Multi-Head Cross-Attention**
3. **Feed-Forward Network**

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

This causal masking is what makes decoder-only models like GPT function as language models: each token can only be influenced by the tokens that came before it.

### 4.2 Cross-Attention

Here, the decoder queries the encoder's output:

- **Queries (Q)** come from the decoder's current state
- **Keys (K) and Values (V)** come from the encoder's output

This is how the decoder "reads" the source sequence. For example, when translating English to Spanish, if the decoder is generating the word *"gato"* (Spanish for *cat*), its Query vector attends to the Keys produced by the encoder. The encoder's representation of the English word *"cat"* will have a high attention score, allowing the decoder to pull the relevant semantic information from the source sentence through the corresponding Value vector.

---

## Step 5: Output Projection and Softmax

After the final decoder layer, a **linear projection** maps the output vectors to vocabulary size, followed by **softmax** to produce a probability distribution over all possible next tokens:

```
Logits = DecoderOutput · W_vocab   [shape: seq_len × vocab_size]
Probabilities = softmax(Logits)
```

The token with the highest probability (or a sampled token) is selected as the next output.

---

## Step 6: Training and Inference

### Training

Transformers are trained using **teacher forcing** — during training, the correct previous tokens are always fed to the decoder (not the model's own predictions), which stabilizes training and allows all output positions to be computed in a single parallel forward pass.

**Loss function:** Cross-entropy loss between predicted token probabilities and the actual next tokens.

**Optimizer:** The original paper used Adam with a custom learning rate schedule:

$$lr = d_{model}^{-0.5} \cdot \min(step^{-0.5},\ step \cdot warmup\_steps^{-1.5})$$

The learning rate increases linearly during the warmup phase, then decays proportionally to `1/√step`. This prevents instability early in training — when weights are random and large updates can be destructive