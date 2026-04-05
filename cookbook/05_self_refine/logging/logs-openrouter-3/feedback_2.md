# Feedback on "How Transformers Work in Deep Learning"

This is well-structured and mostly clear, but has several issues that prevent approval:

## Critical Issues

1. **Incomplete sentence at the end** (Step 6, Training section)
   - "which stabil" is cut off mid-word
   - Complete this thought or remove the dangling text

2. **Inconsistent depth on RoPE explanation**
   - The RoPE paragraph (in Step 2) suddenly becomes much more technical and detailed than surrounding content
   - It reads like it was inserted from a different document
   - Either simplify it to match the surrounding level, or move it to an appendix with a note that it's advanced material

3. **Missing concrete training details** (Step 6)
   - The section promises to explain "Training and Inference" but only hints at teacher forcing before cutting off
   - Add: loss function used (cross-entropy), optimization details, and how inference differs (greedy vs. sampling vs. beam search)
   - This is essential content, not optional

## Moderate Issues

4. **The scaling factor explanation needs clarification**
   - "dot products grow proportionally to `d_k` — since they are sums of `d_k` multiplied terms" is somewhat hand-wavy
   - Better: "Without scaling, the variance of dot products is O(d_k), causing softmax outputs to concentrate on one token"

5. **Attention visualization is illustrative but potentially misleading**
   - The "cat sat on mat" example shows clean, interpretable attention patterns
   - Add a note that real attention patterns are often noisier and less interpretable, especially in early layers

6. **Missing practical considerations**
   - No mention of computational complexity: O(n²) in sequence length for attention (critical limitation)
   - No discussion of why this matters for long sequences
   - Briefly mention linear attention variants or sliding window approaches

## Minor Issues

7. **Decoder-only models explanation** (Step 4 intro)
   - "Because input and output share the same modality — text predicting text" oversimplifies
   - Vision transformers also use decoder-only architectures; the real reason is that language modeling is inherently sequential/autoregressive

8. **Residual connections motivation** (Step 3 intro)
   - Good explanation of *why* they help, but could note that they also help with **feature propagation** — information flows directly through layers without being bottlenecked through the nonlinearity

---

## Summary

**Fix the incomplete sentence immediately.** Then either complete Step 6 or clearly mark it as incomplete. Reconsider the RoPE paragraph's placement and technical level. Add computational complexity discussion. These changes would move this from "good draft" to "publication-ready."