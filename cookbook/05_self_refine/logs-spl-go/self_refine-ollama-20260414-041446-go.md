# SPL Workflow Run: self_refine

- **Status:** complete
- **Adapter:** ollama
- **LLM Calls:** 7
- **Tokens:** 7564 in / 5047 out
- **Latency:** 548353ms
- **Timestamp:** 2026-04-14 04:14:46

## SPL Source

```spl
-- Recipe Name: Self-Refine Pattern
-- Iteratively improves output through critique and refinement

-- Completion anchoring: prompt ends mid-line forcing the model to continue
-- with article content rather than a conversational response.

CREATE FUNCTION draft(task TEXT)
RETURN TEXT
AS $$
You are a professional writer. Write a comprehensive article on the topic below.
Output only the article — no preamble, no notes after.

Topic: {task}
$$;

CREATE FUNCTION critique(current TEXT)
RETURN TEXT
AS $$
You are a professional editor. The article below may have meta-commentary or questions
appended at the end — ignore those, critique only the article body.

If the article needs no further improvement, reply with exactly: [APPROVED]

Otherwise output a numbered list of specific, actionable improvements. Nothing else.

ARTICLE:
{current}

IMPROVEMENTS:
1.

$$;

CREATE FUNCTION refined(task TEXT, current TEXT, feedback TEXT)
RETURN TEXT
AS $$
You are a seasoned writer. Rewrite the draft below incorporating the feedback.
Stay true to the original topic: {task}
Output only the rewritten article — no preamble, no notes after.

DRAFT:
```
{current}
```

FEEDBACK:
```
{feedback}
```
$$;

-- Critique as a self-contained sub-workflow (demonstrates CALL workflow)
WORKFLOW critique_workflow
  INPUT:
    @current TEXT,
    @output_budget INTEGER DEFAULT 2000,
    @critic_model TEXT DEFAULT 'llama3.2'
  OUTPUT: @feedback TEXT
DO
  GENERATE critique(@current) WITH OUTPUT BUDGET @output_budget TOKENS
    USING MODEL @critic_model
    INTO @feedback
  RETURN @feedback
EXCEPTION
  WHEN BudgetExceeded THEN
    RETURN '[APPROVED]' WITH status = 'budget_limit'
END

WORKFLOW self_refine
  INPUT:
    @task TEXT DEFAULT 'What are the benefits of meditation?',
    @output_budget INTEGER DEFAULT 2000,
    @max_iterations INTEGER DEFAULT 3,
    @writer_model TEXT DEFAULT 'llama3.2',
    @critic_model TEXT DEFAULT 'llama3.2',
    @log_dir TEXT DEFAULT 'cookbook/05_self_refine/logs-spl'
  OUTPUT: @result TEXT
DO
  @iteration := 0

  LOGGING f'Self-refine started | max_iterations={@max_iterations} for task:\n {@task}' LEVEL INFO

  -- Initial draft
  GENERATE draft(@task) WITH OUTPUT BUDGET @output_budget TOKENS
    USING MODEL @writer_model
    INTO @current
  LOGGING 'Initial draft ready' LEVEL INFO
  CALL write_file(f'{@log_dir}/draft_0.md', @current) INTO NONE

  -- Iterative refinement loop
  WHILE @iteration < @max_iterations DO
    LOGGING f'\nIteration {@iteration} | critiquing ...' LEVEL INFO
    CALL critique_workflow(@current, @output_budget, @critic_model) INTO @feedback
    CALL write_file(f'{@log_dir}/feedback_{@iteration}.md', @feedback) INTO NONE

    EVALUATE @feedback
      WHEN contains('[APPROVED]') THEN
        LOGGING f'Approved at iteration {@iteration}' LEVEL INFO
        CALL write_file(f'{@log_dir}/final.md', @current) INTO NONE
        RETURN @current WITH status = 'complete', iterations = @iteration
      ELSE
        GENERATE refined(@task, @current, @feedback) WITH OUTPUT BUDGET @output_budget TOKENS
          USING MODEL @writer_model
          INTO @current
        @iteration := @iteration + 1
        CALL write_file(f'{@log_dir}/draft_{@iteration}.md', @current) INTO NONE
        LOGGING f'Refined | iteration={@iteration}' LEVEL INFO
    END
  END

  -- If loop exhausted, commit best effort
  LOGGING f'\nMax iterations reached | iterations={@iteration}' LEVEL WARN
  CALL write_file(f'{@log_dir}/final.md', @current) INTO NONE
  RETURN @current WITH status = 'max_iterations', iterations = @iteration

EXCEPTION
  WHEN MaxIterationsReached THEN
    CALL write_file(f'{@log_dir}/final.md', @current) INTO NONE
    RETURN @current WITH status = 'partial'
  WHEN BudgetExceeded THEN
    RETURN @current WITH status = 'budget_limit'
END

```

## Committed Output

```output
## The Quiet Revolution: Reclaiming Your Inner Calm Through Meditation

In today’s relentlessly paced world, our minds are constantly bombarded with information and demands, leaving us feeling overwhelmed and stressed. Meditation offers a powerful antidote, a practice for reclaiming your inner calm and fostering a deeper connection with yourself. Increasingly recognized as a vital tool for enhancing mental and physical well-being, meditation is backed by a growing body of scientific research demonstrating its transformative potential. This article explores the profound benefits of meditation and how it can fundamentally shift your perspective and improve your life.

**What is Meditation, Really?**

At its core, meditation is a practice of training the mind to focus on the present moment, reducing mental chatter and cultivating awareness. Think of it like strengthening a muscle – with consistent practice, your mind becomes more adept at returning to the “now.” It works by influencing neural plasticity – the brain’s remarkable ability to reorganize itself by forming new neural connections throughout life. Unlike complex spiritual beliefs, meditation doesn’t require specialized equipment, doctrines, or a specific location. While various techniques exist – from focused attention on the breath to loving-kindness meditations to walking meditation – the fundamental goal remains the same: to cultivate a state of present moment awareness and reduce the incessant, often negative, flow of thoughts.

**The Science Behind the Serenity: Research-Backed Benefits**

The benefits of meditation aren’t simply anecdotal; they’re increasingly supported by rigorous scientific research. Here’s a breakdown of the key areas where meditation makes a significant impact:

* **Stress Reduction:** This is perhaps the most well-documented benefit. Meditation activates the parasympathetic nervous system – the “rest and digest” response – counteracting the effects of the sympathetic nervous system (the “fight or flight” response) triggered by stress. Studies, including randomized controlled trials, have shown that regular meditation can reduce cortisol levels by up to 30%, lowers resting blood pressure by an average of 5%, and promotes a sense of calm.

* **Mental Health Enhancement:** Meditation has shown promising results in treating and managing a range of mental health conditions:
    * **Anxiety:** Regular meditation can significantly reduce anxiety symptoms by teaching individuals to observe their thoughts and feelings without judgment, interrupting negative thought patterns and preventing spiraling worry. Studies show symptom reductions of up to 40% in individuals practicing mindfulness meditation for anxiety.
    * **Depression:** Mindfulness meditation, in particular, has been shown to be effective in treating mild to moderate depression, often by shifting focus from ruminative negative thoughts to the present moment. Research suggests that mindfulness meditation can reduce depressive symptoms by as much as 60% in some participants.
    * **PTSD:** Guided meditations focused on grounding techniques – which involve connecting with the body and environment to create a sense of safety – and trauma-informed approaches can help individuals with PTSD manage flashbacks and emotional distress by fostering a sense of control.
    * **ADHD:** Meditation can improve focus and attention by training the mind to resist distractions and strengthen executive function, leading to an average improvement of 20% in attention span, often through a technique called interoceptive exposure.

* **Cognitive Benefits:** Meditation isn’t just about feeling good; it can actually sharpen your mind:
    * **Improved Focus & Attention:** The repetitive nature of many meditation techniques strengthens the brain’s ability to concentrate, increasing grey matter density in areas associated with attention.
    * **Enhanced Memory:** Studies suggest meditation can improve both working memory (short-term recall) and long-term memory, with participants demonstrating up to a 15% improvement in cognitive tests.
    * **Increased Creativity:** By quieting the mind, meditation can create space for new ideas and insights to emerge, fostering divergent thinking.

* **Physical Health Improvements:** The benefits extend beyond the mind:
    * **Pain Management:** Meditation can alter the brain’s perception of pain, reducing its intensity and improving coping mechanisms. Research indicates a 25% reduction in pain intensity for individuals using meditation.
    * **Improved Sleep:** By calming the nervous system, meditation can promote relaxation and improve sleep quality, often leading to a 30-minute reduction in sleep latency.
    * **Boosted Immune System:** Research indicates that meditation can positively influence immune function, increasing activity of natural killer cells by up to 20%.

**Types of Meditation Techniques**

Meditation encompasses a range of approaches, each designed to cultivate different aspects of awareness and inner peace. Mindfulness meditation focuses on observing present-moment experiences without judgment, while focused attention meditation concentrates on a single point, such as the breath. Loving-kindness meditation (Metta) cultivates feelings of compassion and goodwill, promoting positive emotions and social connection. Transcendental Meditation utilizes a mantra to quiet the mind, and walking meditation brings mindfulness to the act of movement
```
