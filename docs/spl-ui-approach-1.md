# SPL UI — Approach 1: Vue 3 + Vite Playground

*Author: Wen G. Gong / Claude*
*Date: 2026-04-18*
*Status: Planned — implementation pending*
*License: Apache 2.0 — community contributions welcome*

---

## Structural Philosophy: Design for Contribution

SPL is Apache 2.0 open source. The author will not implement every UI target —
**the structure must invite community contributors to do so independently.**

The key principle: **each `ui/<framework>/` directory is a self-contained contribution unit.**
A contributor adding `ui/react-native/` touches nothing outside that directory.
They implement one defined interface, follow one README template, and open one PR.

This mirrors how the SPL runtime itself is structured: `spl3`, `spl-go`, `spl-ts` are
independent repos with a shared language contract (`.spl` files + NDD closure). The `ui/`
layer applies the same pattern to frontends: shared runtime contract (SPL.ts ESM API),
independent UI implementations.

---

## Why `ui/` not `web/`

`web/` implies browser-only. `ui/` is the correct abstraction — it covers every surface
where a user interacts with SPL workflows:

| Directory | Platform | Framework | Status |
|-----------|----------|-----------|--------|
| `ui/vue/` | Browser + Desktop PWA | Vue 3 + Vite | **Approach 1 (this doc)** |
| `ui/react/` | Browser + Desktop PWA | React + Vite | Future contribution |
| `ui/react-native/` | iOS + Android | React Native | Future contribution |
| `ui/flutter/` | iOS + Android + Desktop | Flutter / Dart | Future contribution |
| `ui/tauri/` | Native desktop (Win/Mac/Linux) | Tauri + Vue/React | Future contribution |

The SPL.ts runtime (browser-safe ESM) powers all browser-based targets directly.
Mobile/native targets wrap the same `Adapter` interface with platform-native HTTP clients.

---

## Why Vue.js

| Criterion | Vue 3 | React | Svelte |
|-----------|-------|-------|--------|
| Developer familiarity | **User has Vue.js experience** | No | No |
| Bundle size (runtime) | ~34 KB | ~45 KB | ~2 KB |
| Composition API | `<script setup>` — clean, TypeScript-native | Hooks — more boilerplate | Native |
| Monaco integration | `@monaco-editor/loader` — works cleanly | Same | More manual |
| SPL.ts interop | Direct TypeScript imports — no extra glue | Same | Same |
| Ecosystem maturity | Large, stable | Largest | Smaller |
| Static deploy (GH Pages) | Vite build → `dist/` — trivial | Same | Same |

**Decision: Vue 3 with `<script setup>` + Vite.**
The user has Vue experience, the Composition API is idiomatic TypeScript, and the
bundle is slightly lighter than React. All three options would work — Vue wins on
familiarity.

---

## Architecture

```
Browser Tab
├── Vite bundle (Vue 3 + SPL.ts runtime)
│     ├── Monaco Editor          — SPL source with syntax highlighting
│     ├── SPL.ts ESM core        — Lexer / Parser / Executor / Registry
│     │     ├── EchoAdapter      — deterministic, no LLM, instant feedback
│     │     ├── OllamaAdapter    — local Ollama (OLLAMA_ORIGINS=* required)
│     │     ├── OpenAIAdapter    — OpenAI / Groq / Mistral with API key
│     │     └── AnthropicAdapter — Anthropic API with API key
│     ├── Params panel           — key=value INPUT bindings
│     ├── Output panel           — committedValue, status, latency, tokens
│     └── Recipe picker          — built-in starter recipes
└── Static hosting (GitHub Pages / Netlify / Vercel)
```

**No backend server.** The SPL.ts runtime executes entirely in the browser tab.
Ollama requests go directly from the browser to `localhost:11434`.

---

## Repo Location

`ui/vue/` directory inside the `SPL.ts` repo:

```
SPL.ts/
  src/              — runtime (unchanged)
  ui/               — UI root (platform-agnostic container)
    vue/            — Vue 3 browser playground (Approach 1)
      package.json
      vite.config.ts
      tsconfig.json
      index.html
      src/
        main.ts
        App.vue
        components/
          SplEditor.vue      — Monaco editor
          RunBar.vue         — adapter/model selector + Run button
          OutputPanel.vue    — result display
          RecipePicker.vue   — built-in recipes sidebar
        composables/
          useRunner.ts       — SPL execution logic (Lexer→Parser→Executor)
        lib/
          splLanguage.ts     — Monaco SPL token/syntax definition
          recipes.ts         — built-in starter recipes (Hello World, Proxy, Self-Refine)
        style.css
    react/          — (future) React browser implementation
    react-native/   — (future) iOS + Android
    flutter/        — (future) iOS + Android + Desktop
    tauri/          — (future) native desktop (Win/Mac/Linux)
```

The `ui/vue/` app imports the runtime via a Vite alias:
```ts
// vite.config.ts
resolve: { alias: { '@spl': path.resolve(__dirname, '../../src') } }
```
No npm publish step required — both live in the same repo.

The `ui/` layer mirrors the `splc` target matrix: `go/`, `ts/`, `python/` are backend
deployment targets; `ui/vue/`, `ui/react-native/` are UI platform targets. Same DODA
separation of concerns applied to the frontend.

---

## UI Layout

```
┌────────────────────────────────────────────────────────────────┐
│  SPL Playground  v3.0          [adapter ▼] [model] [▶ Run]    │
├─────────────────────┬──────────────────────────────────────────┤
│  Recipes            │                                          │
│  ○ Hello World      │   Monaco Editor                          │
│  ○ Ollama Proxy     │   (SPL source — syntax highlighted)      │
│  ○ Self-Refine      │                                          │
│  ─────────────────  │                                          │
│  Params             ├──────────────────────────────────────────┤
│  key=value          │  Output                                  │
│  (one per line)     │  status: complete  latency: 1588ms       │
│                     │  tokens: 44 in / 23 out                  │
│                     │  ─────────────────────────────────────   │
│                     │  7 * 8 = 56                              │
└─────────────────────┴──────────────────────────────────────────┘
```

---

## Execution Flow (browser)

```ts
// composables/useRunner.ts
import { Lexer }            from '@spl/lexer'
import { Parser }           from '@spl/parser'
import { Executor }         from '@spl/executor'
import { Registry }         from '@spl/registry'
import { EchoAdapter }      from '@spl/adapters/echo'
import { OllamaAdapter }    from '@spl/adapters/ollama'
import { OpenAIAdapter }    from '@spl/adapters/openai'
import { AnthropicAdapter } from '@spl/adapters/anthropic'

async function run(source, adapterName, model, params) {
  const tokens  = new Lexer(source).tokenize()
  const program = new Parser(tokens).parse()

  const registry = new Registry()
  for (const stmt of program.statements) {
    if (stmt.kind === 'WorkflowStatement' || stmt.kind === 'ProcedureStatement')
      registry.registerWorkflow(stmt)
    else if (stmt.kind === 'PromptStatement')
      registry.registerPrompt(stmt)
    else if (stmt.kind === 'CreateFunctionStatement')
      registry.registerFunction(stmt)
  }

  const adapter  = makeAdapter(adapterName, model, ...)
  const executor = new Executor(adapter, registry, 'INFO')

  const workflows = registry.listWorkflows()
  const prompts   = registry.listPrompts()

  if (workflows.length > 0)
    return executor.executeWorkflow(registry.getWorkflow(workflows.at(-1)), params)
  else if (prompts.length > 0)
    return executor.executePrompt(registry.getPrompt(prompts.at(-1))!, params)

  throw new Error('No WORKFLOW or PROMPT found')
}
```

---

## SPL Monaco Language Definition

Registers a Monarch tokenizer for the `spl` language ID covering:

- **Keywords** (blue): `WORKFLOW PROCEDURE INPUT OUTPUT DO END RETURN COMMIT CALL PARALLEL IMPORT GENERATE EVALUATE WHEN THEN ELSE WHILE EXCEPTION RAISE LOGGING LEVEL SELECT FROM WHERE WITH BUDGET TOKENS LIMIT ORDER BY ASC DESC USING MODEL STORE RESULT INTO NONE SET DEFAULT AND OR NOT`
- **Types** (green): `TEXT INT FLOAT BOOL LIST MAP SET IMAGE AUDIO VIDEO STORAGE NUMBER`
- **Literals** (orange): `TRUE FALSE NULL NONE`
- **Variables** (yellow): `@identifier`
- **Functions** (teal): `system_role context memory rag`
- **Strings** (red): `'...'` and `` $$ ... $$ ``
- **Comments** (grey): `-- ...`

---

## Built-in Starter Recipes

| Name | Pattern | Adapter |
|------|---------|---------|
| Hello World | Single `PROMPT` | echo / ollama |
| Ollama Proxy | Parametric `PROMPT` (`prompt=`) | echo / ollama |
| Self-Refine | `WORKFLOW` + `WHILE` + `EVALUATE` | ollama |

These are embedded as TypeScript string constants — no server fetch needed.

---

## Adapter Configuration (browser)

| Adapter | Config needed | Browser constraint |
|---------|--------------|-------------------|
| `echo` | None | Always works |
| `ollama` | Ollama running at `localhost:11434` | Requires `OLLAMA_ORIGINS=*` env var on Ollama |
| `openai` | API key (stored in `localStorage`) | CORS allowed by OpenAI |
| `anthropic` | API key (stored in `localStorage`) | CORS allowed by Anthropic |

The UI shows a one-time setup tip for Ollama CORS when that adapter is selected.

---

## Dependencies

```json
{
  "dependencies": {
    "vue": "^3.4",
    "monaco-editor": "^0.47"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0",
    "vite": "^5.0",
    "typescript": "^5.4"
  }
}
```

`@monaco-editor/loader` loads Monaco lazily from CDN by default; for offline/static
builds, the `monaco-editor` npm package is bundled via `vite-plugin-monaco-editor`.

---

## Deployment

```bash
cd SPL.ts/ui/vue
npm install
npm run build       # → dist/ (static files)
npm run preview     # local preview of dist/

# GitHub Pages
gh-pages -d dist    # or via GitHub Actions workflow
```

Target URL: `https://digital-duck.github.io/SPL.ts/` (or custom domain).

---

## Contribution Interface: How to Add a New UI Target

This is the contract every `ui/<framework>/` directory must fulfil.
A contributor who reads this section knows exactly what to build.

### Required files

```
ui/<framework>/
  README.md         — setup, run, build instructions; link to this doc
  package.json      — (or pubspec.yaml / build.gradle for mobile)
  src/
    useRunner.ts    — (or equivalent) implements the SPL execution interface below
```

### The SPL execution interface

Every UI target wraps the same three-step pattern:

```
parse(source) → register(registry) → execute(adapter, params) → WorkflowResult
```

For browser targets (Vue, React, Svelte), this uses the SPL.ts ESM API directly:

```ts
// The contract every browser UI target must implement
interface SPLRunner {
  run(
    source:      string,                   // .spl source text
    adapterName: string,                   // 'echo' | 'ollama' | 'openai' | 'anthropic'
    model:       string,                   // model name
    params:      Record<string, string>,   // INPUT param bindings
    config:      AdapterConfig,            // API keys, host URLs
  ): Promise<WorkflowResult>
}
```

For mobile/native targets, the same interface applies — only the adapter's HTTP client changes
(React Native `fetch`, Flutter `http` package, etc.).

### The `WorkflowResult` contract

Every UI target renders the same result shape:

```ts
interface WorkflowResult {
  committedValue: string   // the workflow's OUTPUT value → display to user
  status:         string   // 'complete' | 'refused' | 'failed' | custom
  totalLLMCalls:  number
  totalLatencyMs: number
  totalInputToks?: number
  totalOutputToks?: number
}
```

### Required UI components (minimum viable)

| Component | Purpose | Required |
|-----------|---------|----------|
| SPL source editor | Edit or display `.spl` source | Yes (Monaco for browser; CodeMirror or read-only for mobile) |
| Adapter/model selector | Choose echo / ollama / openai | Yes |
| Run button | Trigger `runner.run()` | Yes |
| Output panel | Show `committedValue`, status, latency | Yes |
| Recipe picker | Load a built-in starter recipe | Recommended |

### `splc --lang ui/<framework>` contract (future)

When `splc` gains UI compilation support, the transpiler for `ui/vue` reads the SPL AST
and generates a pre-wired Vue app. To add a new `splc` UI target a contributor:

1. Creates `spl3/splc/transpiler_ui_vue.py` (following `transpiler_ts.py` as template)
2. Registers it in `spl3/splc/cli.py` under `DETERMINISTIC_LANGS`
3. Adds tests to `tests/splc/README.md`
4. No other files change

This is the same pattern used for `go`, `ts`, and `python/langgraph` transpilers —
each is one file + one registration line.

---

## MVP Scope (first PR)

1. Monaco editor with SPL syntax highlighting
2. EchoAdapter run — proves browser execution works with zero config
3. Recipe picker — Hello World, Ollama Proxy, Self-Refine
4. Output panel — committedValue, status, latency
5. OllamaAdapter — local inference for users with Ollama
6. GitHub Pages deploy via CI

Items deferred to follow-on PRs:
- OpenAI / Anthropic adapters with key storage
- Params panel (MVP: hard-code defaults from recipe)
- Momagrid Hub dispatch
- PWA manifest / service worker
- WASM in-browser LLM adapter

---

## Future: `splc --lang ui/vue` — UI as a Compile Target

### The Idea

`splc` today compiles `.spl` to backend runtimes (Go binary, Python/LangGraph, TypeScript Node.js).
A natural extension: compile `.spl` to a **self-contained UI application** — a Vue (or React Native)
frontend that embeds the SPL.ts runtime and exposes the workflow as a polished UI.

```bash
splc my_workflow.spl --lang ui/vue           # → deployable Vue 3 web app
splc my_workflow.spl --lang ui/react-native  # → iOS + Android app (future)
splc my_workflow.spl --lang ui/flutter       # → iOS + Android + Desktop (future)
```

### What it would generate

Given `proxy.spl` (the Ollama proxy recipe), `splc --lang ui/vue` would emit:

```
proxy_ui_vue/
  index.html          — standalone HTML (no server needed)
  App.vue             — pre-wired to proxy workflow's INPUT params
  vite.config.ts
  package.json
  README.md           — "Run: npm install && npm run dev"
```

The generated app would have:
- Input fields auto-generated from the workflow's `INPUT:` block (`@prompt TEXT`, etc.)
- A Run button wired to `executor.executeWorkflow()`
- An output panel showing `committedValue` + latency
- The correct adapter pre-selected (ollama / echo / openai)

### Why it fits the DODA paradigm

| DODA target | Physical artifact | Platform | Audience |
|-------------|-----------------|----------|----------|
| `--lang go` | Static binary | Server / Mini-PC | DevOps engineers |
| `--lang ts` | Node.js script | Server / Edge | Backend JS developers |
| `--lang python/langgraph` | Python module | Cloud pipeline | Data engineers |
| `--lang ui/vue` | Vue 3 web app | Browser / PWA | End users / demos |
| `--lang ui/react-native` | Mobile app | iOS + Android | Mobile users |
| `--lang ui/flutter` | Native app | iOS + Android + Desktop | All devices |

The `.spl` file stays the invariant logical view. `splc --lang ui/vue` is the DODA
path to "deploy this workflow as a UI" — without the developer writing any frontend code.

### Relationship to the SPL Playground

The Playground (`ui/vue/`) is the *general-purpose* SPL IDE — edit any `.spl`, run it, explore
recipes. The `splc --lang ui/vue` target generates a *workflow-specific* app — one INPUT form,
one output panel, deployed directly as a product.

They share the same Vue component library (`SplEditor`, `OutputPanel`, `RunBar`) — the generated
app just pre-configures them with the specific workflow's schema.

### Position in splc roadmap

| Target | Priority | Who | Notes |
|--------|----------|-----|-------|
| `go` | Done | Author | Deterministic transpiler shipped |
| `ts` | Done | Author | Deterministic transpiler shipped |
| `python/langgraph` | Done | Author | Deterministic transpiler shipped |
| `ui/vue` | **Planned** | Author | After Playground MVP — shares component library |
| `ui/react` | Community | Contributor | One transpiler file; React background needed |
| `ui/react-native` | Community | Contributor | Mobile background + React Native needed |
| `ui/flutter` | Community | Contributor | Flutter/Dart background needed |
| `snap` | Author | Future | Ubuntu 26.04 GA required |
| `swift` | Community | Contributor | Apple M4/M5; Swift background needed |

**The open-source contribution model:** the author ships the first target (`ui/vue`) and
establishes the pattern. Community contributors own subsequent targets. Each transpiler is
one Python file — a motivated contributor with the right framework background can deliver
a working target in a weekend. The `tests/splc/README.md` test template is the acceptance
criterion.
