# Using the knowledge base

`knowledge_base/` holds the research material for the current target: the
paper(s), notes, descriptions, prior results, and any human-written direction.
It is **read-only** during improvement iterations.

How to use it:

1. Before changing `target_repo/`, read the material here that is relevant to
   the change you intend to make. The harness passes a truncated index of the
   text files into each iteration prompt; open the originals when you need the
   full detail (PDFs, datasets, long notes).
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
```
