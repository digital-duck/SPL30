# Feedback on "How Transformers Work in Deep Learning"

This is a well-structured, comprehensive guide with excellent pedagogical flow. However, there are specific areas that need refinement:

---

## Critical Issues

### 1. **Incomplete Variants Table**
The final table cuts off:
```
| **DALL-E** | Decoder |
```
Missing the "Key Innovation" column entry. Complete this row or remove it.

### 2. **Inconsistent Notation in Positional Encoding**
The formulas use `2i` and `2i+1` but don't clearly state that even dimensions use sine and odd use cosine. Add:

> "Even dimensions use sine; odd dimensions use cosine."

This matters for readers trying to implement it.

### 3. **Missing Explanation of Scaling Factor**
The `1/√d_k` factor is explained as preventing "extremely large values," but this undersells the issue. Add:

> "Without scaling, large dot products would concentrate softmax probability on a single token, creating near-zero gradients during backpropagation (the saturation problem)."

---

## Moderate Issues

### 4. **Attention Matrix Example Lacks Realism**
The attention matrix shows row sums of 1.0, but the values don't actually sum to 1:
```
The:    [0.6 + 0.2 + 0.05 + 0.05 + 0.05 + 0.05] = 1.0 ✓
cat:    [0.1 + 0.5 + 0.2 + 0.05 + 0.05 + 0.1] = 1.0 ✓
```
Actually, this is correct. **No change needed**, but the formatting could be clearer with explicit totals.

### 5. **Learning Rate Schedule Formula**
The formula is correct but dense. Add a brief explanation:

> "The learning rate increases linearly during warmup, then decays as 1/√step. This prevents training instability early on while allowing fine-tuning later."

### 6. **Computational Complexity Section Oversimplifies**
You state "O(n² · d)" for attention but don't mention that this includes both the attention computation AND the subsequent matrix multiplications. Clarify:

> "Self-attention requires O(n²) comparisons between tokens (quadratic) plus O(n·d²) operations per layer for projections, totaling O(n²·d + n·d²) per layer."

### 7. **Missing Discussion of Inference Efficiency**
You mention training with teacher forcing but don't address **why** autoregressive generation (one token at a time) is necessary at inference. Add:

> "During inference, the model must generate tokens sequentially because each token depends on previous predictions. This makes inference slower than training despite the parallel architecture."

---

## Minor Issues

### 8. **Positional Encoding Alternatives Mentioned But Not Explained**
You reference RoPE and learned embeddings as "modern" alternatives but don't explain why they're better. Either elaborate briefly or remove these mentions.

### 9. **Residual Connection Formula Placement**
The formula appears before its context. Consider moving it into the "Step 3" section where it's first relevant, or introduce it earlier in the architecture overview.

### 10. **Cross-Attention Explanation Could Be Clearer**
The current explanation is correct but abstract. Add a concrete example:

> "In translation, if decoding 'gato' (Spanish for cat), the decoder's Query attends to Keys/Values from the encoder. High attention to the English word 'cat' allows the decoder to copy relevant semantic information."

---

## Strengths to Preserve
- Excellent progression from problem statement to implementation
- Concrete examples (pronoun resolution, "The cat sat on the mat")
- Clear visual diagrams and tables
- Balanced depth for both beginners and practitioners

---

## Summary
**Fix items 1, 2, 3, 5, 6, and 7 before publication.** Items 4, 8, 9, and 10 are optional but recommended for clarity.