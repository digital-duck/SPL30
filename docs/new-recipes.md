### [01] a2a 

```bash
# use ollama
spl3 splc describe $HOME/projects/wgong/PocketFlow/cookbook/pocketflow-a2a/ \
    --lang "Python — PocketFlow" \
    --spec-dir $HOME/projects/digital-duck/SPL30/cookbook-pocketflow/66_a2a/

Describing 7 file(s) in pocketflow-a2a/: a2a_client.py, a2a_server.py, flow.py, main.py, nodes.py, task_manager.py, utils.py
INFO:httpx:HTTP Request: POST http://localhost:11434/v1/chat/completions "HTTP/1.1 200 OK"
Spec written to: /home/gong2/projects/digital-duck/SPL30/cookbook-pocketflow/66_a2a/a2a_ollama-spec.md

Reverse pipeline:
  spl3 text2spl --description "<Section 0 from a2a_client-splc-python_pocketflow-spec.md>" --mode workflow
  spl3 splc compile <output.spl> --lang python/pocketflow

```
Result from using adapter=ollama is not good 


```bash
# use claude_cli
spl3 splc describe $HOME/projects/wgong/PocketFlow/cookbook/pocketflow-a2a/ \
    --lang "Python — PocketFlow" \
    --adapter claude_cli
```

Describing 7 file(s) in pocketflow-a2a/: a2a_client.py, a2a_server.py, flow.py, main.py, nodes.py, task_manager.py, utils.py
Spec written to: /home/gong2/projects/wgong/PocketFlow/cookbook/pocketflow-a2a/a2a_client-splc-python_pocketflow-spec.md


### [02] agent 

```bash
# use claude_cli
spl3 splc describe $HOME/projects/wgong/PocketFlow/cookbook/pocketflow-agent/ \
    --lang "Python — PocketFlow" \
    --adapter claude_cli
```

Describing 4 file(s) in pocketflow-agent/: flow.py, main.py, nodes.py, utils.py
Spec written to: /home/gong2/projects/wgong/PocketFlow/cookbook/pocketflow-agent/flow-splc-python_pocketflow-spec.md


```bash
cd ~/projects/digital-duck/SPL30
pip install -e .

spl3 text2spl --description "/home/gong2/projects/wgong/PocketFlow/cookbook/pocketflow-agent/flow-splc-python_pocketflow-spec.md" \
    --mode workflow \
    --adapter claude_cli \
    -o /home/gong2/projects/digital-duck/SPL/cookbook-pocketflow/pocketflow-agent/pocketflow-agent.spl
```