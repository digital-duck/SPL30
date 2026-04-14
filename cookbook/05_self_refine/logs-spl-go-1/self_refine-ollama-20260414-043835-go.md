# SPL Workflow Run: self_refine

- **Status:** complete
- **Adapter:** ollama
- **LLM Calls:** 3
- **Tokens:** 2440 in / 2236 out
- **Latency:** 214816ms
- **Timestamp:** 2026-04-14 04:38:35

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
## The Quiet Revolution: Unlocking the Powerful Benefits of Meditation

In today’s relentlessly demanding world – a landscape saturated with notifications, constant stimulation, and pervasive anxieties – the practice of meditation has emerged not as a fleeting trend, but as a vital cornerstone of modern well-being. Driven by the pressures of a fast-paced society and a growing awareness of mental health challenges, meditation is gaining widespread recognition not just for its historical roots, but for its increasingly demonstrable impact on our lives. Far from being a New Age indulgence, a growing body of scientific research is powerfully demonstrating the profound and measurable benefits of regular meditation, impacting everything from our mental and emotional health to our physical bodies and cognitive function. But what exactly *is* meditation, and why is it experiencing such remarkable growth in popularity? Let’s delve into the multifaceted advantages of cultivating this ancient practice.

**Understanding Meditation: More Than Just Relaxation**

At its core, meditation is a practice of training the mind to focus and redirect thoughts. Our minds naturally wander, constantly shifting attention between tasks, worries, and memories. This “wandering” isn’t a flaw; it's simply how our brains are wired. There are numerous techniques, but most involve focusing on a specific anchor – a breath, a mantra, a visual image, or bodily sensations – to bring awareness to the present moment. The goal isn’t to eliminate thoughts entirely, which is an incredibly difficult, if not impossible, task, but rather to observe them without judgment and gently guide the focus back to the chosen anchor when the mind inevitably wanders. Think of it like watching clouds drift across the sky – you notice them, but you don’t try to stop them from moving. Different forms include:

* **Mindfulness Meditation:** Focusing on the present moment, noticing thoughts, feelings, and sensations without reacting, allowing them to pass like waves.
* **Loving-Kindness Meditation (Metta):** Cultivating feelings of compassion and goodwill towards oneself and others, starting with a loved one and expanding outwards.
* **Transcendental Meditation (TM):** Utilizing a specific mantra to quiet the mind and promote deep relaxation, often practiced with eyes closed.
* **Walking Meditation:** Bringing mindful awareness to the act of walking, focusing on the sensation of your feet making contact with the ground.


**The Science-Backed Benefits: A Deep Dive**

The benefits of meditation aren’t simply anecdotal; they’re supported by a robust and expanding body of scientific research. Here’s a breakdown of the key areas impacted:

**1. Mental Health & Emotional Regulation:**

* **Reduced Stress & Anxiety:** Meditation significantly lowers cortisol levels – the hormone associated with stress – and activates the parasympathetic nervous system, promoting a state of calm. Research published in the *Journal of the American Medical Association* has shown that regular meditation can be as effective as, or even more effective than, traditional therapies like Cognitive Behavioral Therapy (CBT) for managing anxiety disorders.
* **Combating Depression:** Mindfulness meditation, in particular, can be a powerful tool in treating depression. Studies, including research from Harvard Medical School, indicate that it helps individuals detach from negative thought patterns and develop a more accepting and resilient mindset, sometimes even complementing antidepressant medication.
* **Improved Focus & Attention:** Regular meditation strengthens the prefrontal cortex, the brain region responsible for focus, attention, and executive function. This translates to improved concentration, productivity, and the ability to resist distractions – for example, students practicing mindfulness meditation have shown improved test scores and sustained attention during lectures.
* **Increased Self-Awareness:** Meditation fosters a deeper understanding of one’s thoughts, emotions, and behaviors, leading to greater self-awareness and emotional intelligence, allowing individuals to respond to situations with greater intention.

**2. Physical Health & Wellbeing:**

* **Lower Blood Pressure:** Studies have shown that meditation can help lower both systolic and diastolic blood pressure, a significant factor in preventing heart disease – research published in *Hypertension* demonstrated an average reduction of 5 mmHg in both blood pressure readings for participants practicing meditation.
* **Pain Management:** Mindfulness meditation has been shown to reduce the perception of pain by altering the brain’s pain signals and promoting relaxation. It’s particularly effective in managing chronic pain conditions like fibromyalgia and arthritis, with some studies showing a significant decrease in pain medication reliance.
* **Immune System Boost:** Research suggests meditation can positively influence the immune system, potentially increasing the production of antibodies and improving the body’s ability to fight off infections – a meta-analysis published in *Psychosomatic Medicine* found a correlation between meditation and improved immune function.
* **Improved Sleep:** By calming the mind and reducing anxiety, meditation can significantly improve sleep quality and help combat insomnia.

**3. Cognitive Benefits:**

* **Enhanced Memory:** Mindfulness meditation has been linked to improved memory function, particularly working
```
