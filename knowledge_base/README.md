# knowledge_base/

The research material the agent reads while improving `target_repo/`: papers,
notes, descriptions, prior results, and human-written directions or constraints.

```text
knowledge_base/
  AGENTS.md      how the agent should use this directory (read-only guidance)
  README.md      this file
  paper.pdf      e.g. the paper                         (you provide)
  notes.md       e.g. your summary / key equations      (you provide)
  directions.md  e.g. what to try, constraints          (you provide)
```

The harness includes a truncated index of the text files here in every
iteration prompt, and `AGENTS.md` is loaded as a standing OpenCode instruction.

## What gets committed

By default the material you drop in here is **git-ignored** (see
`.gitignore`), so the harness repo stays minimal and generic — only `AGENTS.md`
and this `README.md` are tracked. If you want to version a specific knowledge
base with the repo, force-add it (`git add -f knowledge_base/notes.md`) or edit
`knowledge_base/.gitignore`.
