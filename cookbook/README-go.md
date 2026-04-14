● FEATURES.md is already updated — I did that at the end of the last step, marking recipes 05, 50, 63, 64 as [DONE] ¹ for 
  spl-go with the footnote explaining echo-adapter verification.
                                                                                                                          
Yes, that's exactly the right plan:
                                                                                                                        
1. You run the four recipes with --adapter ollama (live LLM)                                                            
2. If they pass — upgrade [DONE] ¹ to [DONE] (drop the footnote qualifier) in FEATURES.md
3. If a new error surfaces — it'll be an executor-level issue (variable binding, OUTPUT handling, etc.), not a parser   
issue, so we fix it there                                                                                               
                                                                                                                        
The commands to run:                                                                                                    
```bash
cd ~/projects/digital-duck/SPL30

spl-go run cookbook/05_self_refine/self_refine.spl \
    --adapter ollama \
    --param writer_model="gemma3" \
    --param critic_model="gemma3" \
    --param max_iterations=1

spl-go run cookbook/50_code_pipeline/code_pipeline.spl \
    --adapter ollama \
    --param model="gemma3" \
    --param log_dir="cookbook/50_code_pipeline/logs-spl-go" \
    --param spec="write a Python function that reverses a string" 

export SPEC="write a Python function reverse_string(s: str) -> str that returns the input string with characters in reverse order, handles empty string by returning empty string"
export MODEL="gemma4:e4b"            #   "gemma3"
spl-go run cookbook/50_code_pipeline/code_pipeline.spl \
    --adapter ollama \
    --param model="$MODEL" \
    --param log_dir="cookbook/50_code_pipeline/logs-spl-go" \
    --param spec="$SPEC" 


spl-go run cookbook/63_parallel_code_review/parallel_code_review.spl \
    --adapter ollama \
    --param model="gemma4:e4b" \
    --param code="def add(a, b): return a - b"

spl-go run cookbook/64_parallel_news_digest/parallel_news_digest.spl \
    --adapter ollama \
    --param model="gemma4:e4b" \
    --param topic="AI"
```                                                                                                                  
Run them from the SPL30/ directory so relative IMPORT paths resolve correctly.       