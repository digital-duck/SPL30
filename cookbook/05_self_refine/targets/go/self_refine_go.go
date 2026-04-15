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
  if resp.StatusCode != http.StatusOK { return "", fmt.Errorf("ollama error: %d", resp.StatusCode) }
  var out generateResponse
  if err := json.NewDecoder(resp.Body).Decode(&out); err != nil { return "", err }
  return strings.TrimSpace(out.Response), nil
}

func writeFile(path, content string) {
  os.MkdirAll(filepath.Dir(path), 0755)
  os.WriteFile(path, []byte(content), 0644)
}

func critiqueWorkflow(current string, output_budget int, critic_model string, ollamaHost string) (result string, status string, iterations int, err error) {
  var feedback string
  feedback, err = generate(ollamaHost, critic_model, fmt.Sprintf(critiquePrompt, current))
  if err != nil { return "", "error", 0, err }
  return feedback, "complete", 0, nil
}

func selfRefine(task string, output_budget int, max_iterations int, writer_model string, critic_model string, log_dir string, ollamaHost string) (result string, status string, iterations int, err error) {
  var current string
  var feedback string
  var iteration int
  iteration = 0
  log.Printf("Self-refine started | max_iterations=%v for task:\n %v", max_iterations, task)
  current, err = generate(ollamaHost, writer_model, fmt.Sprintf(draftPrompt, task))
  if err != nil { return "", "error", 0, err }
  log.Printf("Initial draft ready")
  writeFile(fmt.Sprintf("%v/draft_0.md", log_dir), current)
  for iteration < max_iterations {
    log.Printf("\nIteration %v | critiquing ...", iteration)
    feedback, _, _, err = critiqueWorkflow(current, output_budget, critic_model, ollamaHost)
    if err != nil { return "", "error", 0, err }
    writeFile(fmt.Sprintf("%v/feedback_%v.md", log_dir, iteration), feedback)
    if strings.Contains(feedback, "[APPROVED]") {
      log.Printf("Approved at iteration %v", iteration)
      writeFile(fmt.Sprintf("%v/final.md", log_dir), current)
      return current, "complete", iteration, nil
    } else {
      current, err = generate(ollamaHost, writer_model, fmt.Sprintf(refinedPrompt, task, current, feedback))
      if err != nil { return "", "error", 0, err }
      iteration = (iteration + 1)
      writeFile(fmt.Sprintf("%v/draft_%v.md", log_dir, iteration), current)
      log.Printf("Refined | iteration=%v", iteration)
    }
  }
  log.Printf("\nMax iterations reached | iterations=%v", iteration)
  writeFile(fmt.Sprintf("%v/final.md", log_dir), current)
  return current, "max_iterations", iteration, nil
}


func main() {
  task := flag.String("task", "What are the benefits of meditation?", "task")
  output_budget := flag.Int("output-budget", 2000, "output_budget")
  max_iterations := flag.Int("max-iterations", 3, "max_iterations")
  writer_model := flag.String("writer-model", "llama3.2", "writer_model")
  critic_model := flag.String("critic-model", "llama3.2", "critic_model")
  log_dir := flag.String("log-dir", "cookbook/05_self_refine/logs-spl", "log_dir")
  flag.Parse()
  res, status, iters, err := selfRefine(*task, *output_budget, *max_iterations, *writer_model, *critic_model, *log_dir, "http://localhost:11434")
  if err != nil { log.Fatal(err) }
  fmt.Printf("Status: %s, Iters: %d\n%s\n", status, iters, res)
}
