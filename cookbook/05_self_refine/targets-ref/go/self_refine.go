// splc-generated: self_refine.spl → go target
//
// Source:  cookbook/05_self_refine/self_refine.spl
// Command: splc --target go cookbook/05_self_refine/self_refine.spl
//
// Runtime: Ollama REST API (http://localhost:11434)
// Models:  any Ollama-hosted model (default: gemma3 / llama3.2)
//
// Usage:
//   go run self_refine.go --task "Write a haiku about coding"
//   go run self_refine.go --task "Explain recursion" --max-iterations 3
//   go build -o self_refine && ./self_refine --task "Write a haiku about coding"

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

// ── Prompts ─────────────────────────────────────────────────────────────────
// SPL equivalent: CREATE FUNCTION ... AS $$ ... $$

const draftPrompt = `You are a professional writer. Write a comprehensive article on the topic below.
Output only the article — no preamble, no notes after.

Topic: %s`

const critiquePrompt = `You are a professional editor. The article below may have meta-commentary or questions
appended at the end — ignore those, critique only the article body.

If the article needs no further improvement, reply with exactly: [APPROVED]

Otherwise output a numbered list of specific, actionable improvements. Nothing else.

ARTICLE:
%s

IMPROVEMENTS:
1.`

// refinedPrompt uses string concat to embed literal backticks inside the template.
const refinedPrompt = "You are a seasoned writer. Rewrite the draft below incorporating the feedback.\n" +
	"Stay true to the original topic: %s\n" +
	"Output only the rewritten article — no preamble, no notes after.\n\n" +
	"DRAFT:\n```\n%s\n```\n\n" +
	"FEEDBACK:\n```\n%s\n```"

// ── Ollama client ─────────────────────────────────────────────────────────────
// SPL equivalent: GENERATE func(...) USING MODEL @model INTO @var

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
	if err != nil {
		return "", fmt.Errorf("marshal: %w", err)
	}

	resp, err := http.Post(
		ollamaHost+"/api/generate",
		"application/json",
		bytes.NewReader(body),
	)
	if err != nil {
		return "", fmt.Errorf("POST /api/generate: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		raw, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("ollama HTTP %d: %s", resp.StatusCode, raw)
	}

	var out generateResponse
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return "", fmt.Errorf("decode response: %w", err)
	}
	return strings.TrimSpace(out.Response), nil
}

// ── File writer ──────────────────────────────────────────────────────────────
// SPL equivalent: CALL write_file(@path, @content) INTO NONE

func writeFile(path, content string) {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		log.Printf("WARN: mkdir %s: %v", filepath.Dir(path), err)
		return
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		log.Printf("WARN: write %s: %v", path, err)
	}
}

// ── WORKFLOW self_refine ──────────────────────────────────────────────────────
// SPL equivalent:
//   WORKFLOW self_refine
//     INPUT:  @task, @output_budget, @max_iterations, @writer_model, @critic_model, @log_dir
//     OUTPUT: @result TEXT
//   DO ... END

func selfRefine(
	task        string,
	maxIter     int,
	writerModel string,
	criticModel string,
	logDir      string,
	ollamaHost  string,
) (result string, status string, iterations int, err error) {

	// SPL: @iteration := 0
	iteration := 0

	// SPL: LOGGING f'Self-refine started | max_iterations=...' LEVEL INFO
	log.Printf("Self-refine started | max_iterations=%d for task:\n%s", maxIter, task)

	// SPL: GENERATE draft(@task) WITH OUTPUT BUDGET @output_budget TOKENS
	//       USING MODEL @writer_model INTO @current
	log.Println("Generating initial draft ...")
	current, err := generate(ollamaHost, writerModel, fmt.Sprintf(draftPrompt, task))
	if err != nil {
		return "", "error", 0, fmt.Errorf("draft: %w", err)
	}
	writeFile(filepath.Join(logDir, "draft_0.md"), current)
	log.Println("Initial draft ready")

	// SPL: WHILE @iteration < @max_iterations DO
	for iteration < maxIter {
		// SPL: LOGGING f'Iteration {@iteration} | critiquing ...' LEVEL DEBUG
		log.Printf("Iteration %d | critiquing ...", iteration)

		// SPL: GENERATE critique(@current) USING MODEL @critic_model INTO @feedback
		feedback, err := generate(ollamaHost, criticModel, fmt.Sprintf(critiquePrompt, current))
		if err != nil {
			return current, "error", iteration, fmt.Errorf("critique: %w", err)
		}
		writeFile(filepath.Join(logDir, fmt.Sprintf("feedback_%d.md", iteration)), feedback)

		// SPL: EVALUATE @feedback WHEN contains('[APPROVED]') THEN
		if strings.Contains(feedback, "[APPROVED]") {
			// SPL: LOGGING f'Approved at iteration {@iteration}' LEVEL INFO
			log.Printf("Approved at iteration %d", iteration)
			writeFile(filepath.Join(logDir, "final.md"), current)
			// SPL: RETURN @current WITH status = 'complete', iterations = @iteration
			return current, "complete", iteration, nil
		}

		// SPL: ELSE → GENERATE refined(@task, @current, @feedback) INTO @current
		log.Printf("Iteration %d | refining ...", iteration)
		current, err = generate(ollamaHost, writerModel, fmt.Sprintf(refinedPrompt, task, current, feedback))
		if err != nil {
			return current, "error", iteration, fmt.Errorf("refine: %w", err)
		}
		iteration++
		writeFile(filepath.Join(logDir, fmt.Sprintf("draft_%d.md", iteration)), current)
		log.Printf("Refined | iteration=%d", iteration)
	}

	// SPL: LOGGING f'Max iterations reached | iterations={@iteration}' LEVEL WARN
	log.Printf("WARN: Max iterations reached | iterations=%d", iteration)
	writeFile(filepath.Join(logDir, "final.md"), current)
	// SPL: RETURN @current WITH status = 'max_iterations', iterations = @iteration
	return current, "max_iterations", iteration, nil
}

// ── Entry point ──────────────────────────────────────────────────────────────
// SPL: `spl run self_refine.spl task="..." --adapter ollama`
// Go:  `go run self_refine.go --task "..."`

func main() {
	// SPL: INPUT parameters → CLI flags
	task        := flag.String("task",          "What are the benefits of meditation?", "Task to refine")
	maxIter     := flag.Int("max-iterations",   3,              "Maximum refinement iterations")
	writerModel := flag.String("writer-model",  "llama3.2",     "Ollama model for draft + refine")
	criticModel := flag.String("critic-model",  "llama3.2",     "Ollama model for critique")
	logDir      := flag.String("log-dir",       "logs-go",      "Directory for draft/feedback/final files")
	ollamaHost  := flag.String("ollama-host",   "http://localhost:11434", "Ollama server URL")
	flag.Parse()

	start := time.Now()

	result, status, iters, err := selfRefine(
		*task, *maxIter, *writerModel, *criticModel, *logDir, *ollamaHost,
	)

	elapsed := time.Since(start).Round(time.Millisecond)
	log.Printf("Done | status=%s  iterations=%d  elapsed=%s", status, iters, elapsed)

	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
		os.Exit(1)
	}

	fmt.Println()
	fmt.Println(strings.Repeat("=", 60))
	fmt.Println(result)
}
