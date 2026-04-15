// splc-generated: deterministic go target
package main

import (
  "bytes"
  "encoding/json"
  "flag"
  "fmt"
  "io"
  "log"
  "net/http"
  "os"
  "path/filepath"
  "strings"
  "time"
)

const draftPrompt = `
You are a professional writer. Write a comprehensive article on the topic below.
Output only the article — no preamble, no notes after.

Topic: %s
`

const critiquePrompt = `
You are a professional editor. The article below may have meta-commentary or questions
appended at the end — ignore those, critique only the article body.

If the article needs no further improvement, reply with exactly: [APPROVED]

Otherwise output a numbered list of specific, actionable improvements. Nothing else.

ARTICLE:
%s

IMPROVEMENTS:
1.

`

const refinedPrompt = `
You are a seasoned writer. Rewrite the draft below incorporating the feedback.
Stay true to the original topic: %s
Output only the rewritten article — no preamble, no notes after.

DRAFT:
` + "`" + `` + "`" + `` + "`" + `
%s
` + "`" + `` + "`" + `` + "`" + `

FEEDBACK:
` + "`" + `` + "`" + `` + "`" + `
%s
` + "`" + `` + "`" + `` + "`" + `
`

type generateRequest struct {
  Model  string `json:"model"`
  Prompt string `json:"prompt"`
  Stream bool   `json:"stream"`
}

type generateResponse struct {
  Response string `json:"response"`
}

func generate(ollamaHost, model, prompt string) (string, error) {
  body, err := json.Marshal(generateRequest{
    Model:  model,
    Prompt: prompt,
    Stream: false,
  })
  if err != nil { return "", err }
  resp, err := http.Post(ollamaHost+"/api/generate", "application/json", bytes.NewReader(body))
  if err != nil { return "", err }
  defer resp.Body.Close()
  if resp.StatusCode != http.StatusOK {
    raw, _ := io.ReadAll(resp.Body)
    return "", fmt.Errorf("ollama HTTP %d: %s", resp.StatusCode, raw)
  }
  var out generateResponse
  if err := json.NewDecoder(resp.Body).Decode(&out); err != nil { return "", err }
  return strings.TrimSpace(out.Response), nil
}

func writeFile(path, content string) {
  if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
    log.Printf("writeFile: mkdir %s: %v", path, err)
    return
  }
  if err := os.WriteFile(path, []byte(content), 0644); err != nil {
    log.Printf("writeFile: %v", err)
  }
}

func critiqueWorkflow(current string, output_budget int, critic_model string, ollamaHost string) (result string, status string, iterations int, err error) {
  var feedback string

  // SPL: EXCEPTION
  defer func() {
    if r := recover(); r != nil {
      type splErr interface { SPLType() string }
      if e, ok := r.(splErr); ok {
        switch e.SPLType() {
        case "BudgetExceeded":
          // SPL: WHEN BudgetExceeded THEN
          // SPL: COMMIT '[APPROVED]'
          result = "[APPROVED]"
          status = "budget_limit"
          iterations = 0
        }
      }
    }
  }()

  // SPL: GENERATE critique(current) USING MODEL @critic_model WITH OUTPUT BUDGET @output_budget TOKENS INTO feedback
  feedback, err = generate(ollamaHost, critic_model, fmt.Sprintf(critiquePrompt, current))
  if err != nil { return "", "error", 0, err }
  // SPL: COMMIT feedback
  return feedback, "complete", 0, nil
}

func selfRefine(task string, output_budget int, max_iterations int, writer_model string, critic_model string, log_dir string, ollamaHost string) (result string, status string, iterations int, err error) {
  var current string
  var feedback string
  var iteration int

  // SPL: EXCEPTION
  defer func() {
    if r := recover(); r != nil {
      type splErr interface { SPLType() string }
      if e, ok := r.(splErr); ok {
        switch e.SPLType() {
        case "MaxIterationsReached":
          // SPL: WHEN MaxIterationsReached THEN
          // SPL: CALL write_file(f'{@log_dir}/final.md', current)
          writeFile(fmt.Sprintf("%v/final.md", log_dir), current)
          // SPL: COMMIT current
          result = current
          status = "partial"
          iterations = iteration
        case "BudgetExceeded":
          // SPL: WHEN BudgetExceeded THEN
          // SPL: COMMIT current
          result = current
          status = "budget_limit"
          iterations = iteration
        }
      }
    }
  }()

  // SPL: iteration := 0
  iteration = 0
  // SPL: LOGGING f'Self-refine started | max_iterations={@max_iterations} for task:\n {@task}'
  log.Printf("Self-refine started | max_iterations=%v for task:\n %v", max_iterations, task)
  // SPL: GENERATE draft(task) USING MODEL @writer_model WITH OUTPUT BUDGET @output_budget TOKENS INTO current
  current, err = generate(ollamaHost, writer_model, fmt.Sprintf(draftPrompt, task))
  if err != nil { return "", "error", 0, err }
  // SPL: LOGGING 'Initial draft ready'
  log.Printf("Initial draft ready")
  // SPL: CALL write_file(f'{@log_dir}/draft_0.md', current)
  writeFile(fmt.Sprintf("%v/draft_0.md", log_dir), current)
  // SPL: WHILE iteration < max_iterations DO
  for iteration < max_iterations {
    // SPL: LOGGING f'\nIteration {@iteration} | critiquing ...'
    log.Printf("\nIteration %v | critiquing ...", iteration)
    // SPL: CALL critique_workflow(current, output_budget, critic_model) INTO feedback
    feedback, _, _, err = critiqueWorkflow(current, output_budget, critic_model, ollamaHost)
    if err != nil { return "", "error", 0, err }
    // SPL: CALL write_file(f'{@log_dir}/feedback_{@iteration}.md', feedback)
    writeFile(fmt.Sprintf("%v/feedback_%v.md", log_dir, iteration), feedback)
    // SPL: EVALUATE feedback ...
    if strings.Contains(feedback, "[APPROVED]") {
      // SPL: LOGGING f'Approved at iteration {@iteration}'
      log.Printf("Approved at iteration %v", iteration)
      // SPL: CALL write_file(f'{@log_dir}/final.md', current)
      writeFile(fmt.Sprintf("%v/final.md", log_dir), current)
      // SPL: COMMIT current
      return current, "complete", iteration, nil
    } else {
      // SPL: GENERATE refined(task, current, feedback) USING MODEL @writer_model WITH OUTPUT BUDGET @output_budget TOKENS INTO current
      current, err = generate(ollamaHost, writer_model, fmt.Sprintf(refinedPrompt, task, current, feedback))
      if err != nil { return "", "error", 0, err }
      // SPL: iteration := BinaryOp(left=ParamRef(name='iteration'), op='+', right=Literal(value=1, literal_type='integer'))
      iteration = (iteration + 1)
      // SPL: CALL write_file(f'{@log_dir}/draft_{@iteration}.md', current)
      writeFile(fmt.Sprintf("%v/draft_%v.md", log_dir, iteration), current)
      // SPL: LOGGING f'Refined | iteration={@iteration}'
      log.Printf("Refined | iteration=%v", iteration)
    }
  }
  // SPL: LOGGING f'\nMax iterations reached | iterations={@iteration}'
  log.Printf("\nMax iterations reached | iterations=%v", iteration)
  // SPL: CALL write_file(f'{@log_dir}/final.md', current)
  writeFile(fmt.Sprintf("%v/final.md", log_dir), current)
  // SPL: COMMIT current
  return current, "max_iterations", iteration, nil
}

func main() {
  task := flag.String("task", "What are the benefits of meditation?", "task")
  output_budget := flag.Int("output-budget", 2000, "output_budget")
  max_iterations := flag.Int("max-iterations", 3, "max_iterations")
  writer_model := flag.String("writer-model", "llama3.2", "writer_model")
  critic_model := flag.String("critic-model", "llama3.2", "critic_model")
  log_dir := flag.String("log-dir", "cookbook/05_self_refine/logs-spl", "log_dir")
  ollamaHost := flag.String("ollama-host", "http://localhost:11434", "Ollama server URL")
  flag.Parse()
  start := time.Now()
  res, status, iters, err := selfRefine(*task, *output_budget, *max_iterations, *writer_model, *critic_model, *log_dir, *ollamaHost)
  if err != nil { log.Fatal(err) }
  log.Printf("Done | status=%s  iterations=%d  elapsed=%.1fs", status, iters, time.Since(start).Seconds())
  fmt.Printf("\n%s\n%s\n", strings.Repeat("=", 60), res)
}
