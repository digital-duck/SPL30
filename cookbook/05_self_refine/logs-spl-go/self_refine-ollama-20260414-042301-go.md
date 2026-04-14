# SPL Workflow Run: self_refine

- **Status:** complete
- **Adapter:** ollama
- **LLM Calls:** 2
- **Tokens:** 1104 in / 1430 out
- **Latency:** 125070ms
- **Timestamp:** 2026-04-14 04:23:01

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
## Unlock Your Potential: The Profound Benefits of Meditation

In today’s relentlessly paced world, stress, anxiety, and a constant feeling of being overwhelmed have become disturbingly commonplace. While numerous approaches to managing these challenges exist, meditation – a practice rooted in ancient traditions – is gaining widespread recognition as a powerful, accessible, and scientifically-backed tool for improving both mental and physical well-being. But what exactly are the benefits of meditation, and why is it experiencing such a surge in popularity? Let’s delve into the multifaceted advantages this simple yet profound practice offers.

**The Science Behind the Stillness: How Meditation Works**

At its core, meditation involves training the mind to focus and redirect thoughts. It’s not about emptying your mind entirely – that’s often an unrealistic goal – but rather about observing your thoughts without judgment and gently returning your attention to a chosen anchor, such as your breath, a mantra, or a visual image. This process triggers a cascade of neurological changes, primarily within the prefrontal cortex, the area of the brain responsible for executive functions like attention, decision-making, and emotional regulation.

**The Extensive Benefits – A Breakdown**

The research supporting the benefits of meditation is mounting, spanning numerous disciplines from neuroscience to psychology to medicine. Here’s a detailed look at what meditation can do for you:

* **Stress Reduction:** This is arguably the most well-known benefit. Meditation activates the parasympathetic nervous system – the “rest and digest” response – counteracting the effects of the “fight or flight” response triggered by stress. Studies consistently demonstrate a significant reduction in cortisol levels (the stress hormone) after regular meditation practice.

* **Anxiety Management:** Meditation, particularly mindfulness meditation, helps individuals detach from anxious thoughts and rumination. By observing anxieties without getting caught up in them, practitioners can reduce their intensity and frequency. Techniques like loving-kindness meditation can specifically target negative self-talk and foster feelings of compassion.

* **Improved Focus and Attention:** The deliberate practice of focusing on a single point, such as your breath, strengthens the neural pathways associated with attention and concentration. This translates into improved focus in daily life, making it easier to concentrate on tasks, work, and studies.

* **Emotional Regulation:** Meditation cultivates self-awareness, allowing you to recognize and understand your emotions as they arise. This increased awareness prevents emotional reactions from spiraling out of control and fosters greater emotional stability.

* **Reduced Symptoms of Depression:** Research indicates that meditation can be an effective adjunct therapy for depression, particularly when combined with traditional treatments like psychotherapy and medication. It helps shift focus away from negative thoughts and promotes a sense of calm and well-being.

* **Pain Management:** Surprisingly, meditation can actually alter the way the brain perceives pain. By reducing stress and increasing body awareness, it can help individuals cope with chronic pain conditions like fibromyalgia and arthritis.

* **Enhanced Self-Awareness:** Through regular practice, meditation fosters a deeper understanding of your thoughts, feelings, and behaviors. This heightened self-awareness can lead to greater personal growth and improved relationships.

* **Improved Sleep:** A calm, focused mind is a restful mind. Meditation can quiet the mental chatter that often keeps us awake at night, promoting deeper and more restorative sleep.

* **Potential Physical Health Benefits:** Emerging research suggests meditation may contribute to lowering blood pressure, boosting the immune system, and even increasing lifespan – although more long-term studies are needed in this area.


**Getting Started with Meditation – It’s Easier Than You Think**

You don’t need an expensive guru or a special studio to reap the benefits of meditation. Here are a few simple ways to begin:

* **Start Small:** Begin with just 5-10 minutes a day and gradually increase the duration as you become more comfortable.
* **Find a Quiet Space:** Choose a place where you won’t be disturbed.
* **Focus on Your Breath:** Pay attention to the sensation of your breath entering and leaving your body.
* **Use Guided Meditations:** Numerous apps and online resources offer guided meditations for beginners.
* **Be Patient:** Meditation is a skill that takes time and practice to develop. Don’t get discouraged if your mind wanders – simply gently redirect your attention back to your anchor.

**Conclusion**

Meditation is not a quick fix, but a transformative practice that can profoundly impact your life. By cultivating stillness, awareness, and compassion, it offers a powerful pathway to improved mental and physical well-being.  Whether you’re seeking stress relief, enhanced focus, or simply a greater sense of peace, incorporating meditation into your daily routine could unlock your potential and lead to a more fulfilling and balanced life. 

```
