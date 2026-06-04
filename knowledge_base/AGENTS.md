# Using the knowledge base

`knowledge_base/` holds the research material for the current target: the
paper(s), notes, descriptions, prior results, and any human-written direction.
It is **read-only** during improvement iterations.

How to use it:

1. Before changing `target_repo/`, consult the material relevant to your intended
   change. The harness inlines the small curated notes here in full and lists every
   file (large notes, papers, PDFs) in a manifest in each iteration prompt. For anything
   not inlined, ask the `kb-researcher` subagent a SPECIFIC question (by name or
   `@kb-researcher`) — it reads the material in an isolated context and returns distilled
   findings with citations, so the main context stays clean. Read large files yourself only
   if the subagent is unavailable, and then only the parts you need (`pdftotext <file> -`
   for PDFs under OpenCode).
2. Ground every change in this material plus the prior outcomes in `state/`.
   Prefer hypotheses the paper or directions actually motivate.
3. Treat direction/constraint files here as binding (e.g. "do not increase
   inference time by more than 10%", "prefer small reversible changes").
4. Do not edit anything under `knowledge_base/`.

Suggested files to drop in (all optional):

```text
knowledge_base/paper.pdf          the paper itself
knowledge_base/notes.md           your summary / key equations / ablations
knowledge_base/directions.md      what to try, what to avoid, constraints
knowledge_base/library/           bulky papers, datasets, long references —
                                  never inlined; always extracted on demand
```

Anything placed under `knowledge_base/library/` is kept out of the main context
regardless of size, and is reached only through the `kb-researcher` subagent.
