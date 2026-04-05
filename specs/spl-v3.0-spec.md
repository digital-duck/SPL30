# SPL v3.0 Specification: DODA & Multi-Modal Orchestration

## 1. Multi-Modality Definition
SPL v3.0 promotes non-text modalities to first-class citizens. Data sources are referenced via the `@` symbol and processed via modality-specific methods.

### 1.1 Grammar Extensions
```sql
-- Method: audio.listen() or audio.transcribe()
-- Method: vision.analyze() or vision.ocr()
-- Method: video.track() or video.summarize()