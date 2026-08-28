---
name: new-module
description: Scaffold a new module as a vertical slice that honors the project's modularity rules
disable-model-invocation: true
argument-hint: [domain] [use-case, e.g. user change-password]
---

Scaffold a new module for: $ARGUMENTS

1. Look at one existing slice in this codebase and copy its layout, naming, and test conventions exactly. If this is the first slice, use: a domain directory containing a use-case directory holding the entry point, validation, core logic, and its tests side by side.
2. Create the slice with:
   - A single published entry point (the module's interface — the only thing other modules may import)
   - Input validation at the boundary
   - A test file with one passing smoke test and TODO cases named after the behaviors the module must have
3. Wire it into the app the same way sibling slices are wired (routing, registry, DI — follow the existing pattern).
4. Enforce the boundaries: the slice must not import another slice's internals, and nothing outside may import anything except the entry point. State which imports you chose and why.
5. Run the smoke test and the linter; show output.

Keep it simple: no configuration options, interfaces, or generalization the use case doesn't need today. The slice should be small enough to read in one sitting.
