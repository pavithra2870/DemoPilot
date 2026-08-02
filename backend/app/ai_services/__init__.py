"""AI orchestration and reusable AI capabilities.

Split from `app.services` on purpose: everything here knows about models,
prompts, retrieval and agent state. Everything in `app.services` is business
logic that would still exist if the AI were swapped for a human.
"""
