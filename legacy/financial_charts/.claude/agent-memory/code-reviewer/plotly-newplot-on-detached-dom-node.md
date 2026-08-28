---
name: plotly-newplot-on-detached-dom-node
description: web/templates/index.html called Plotly.newPlot() on a card/plotDiv before it was ever attached to the document — every chart would render 0x0/blank on load
metadata:
  type: project
---

Found 2026-07-26/27 reviewing the interactive-Plotly-dashboard change (`feature/source-commissioning`,
`web/templates/index.html`, replacing the iframe/static-PNG render). `renderCard(container, spec)`
built `card`/`plotDiv` via `document.createElement`, called `Plotly.newPlot(plotDiv, ...)` while
`plotDiv` was only attached to the still-detached `card`, and only did `container.appendChild(card)`
*after* that call returned. Worse, `renderDashboard()` built the whole `grid` off-DOM and looped
`data.charts.forEach(renderCard)` — i.e. every single `renderCard` call, and therefore every single
`Plotly.newPlot` call — happened before `results.appendChild(grid)` ever ran. So every chart on every
render was plotted into a container with zero computed layout size (an element not connected to
`document` has no box model at all, not just `display:none`).

**Why:** this is a well-known Plotly footgun (same class as "chart renders blank in a hidden tab/
modal until you resize the window") — `Plotly.newPlot` measures the container's `getBoundingClientRect()`
at call time; a detached node reports 0x0, so the initial SVG renders with zero/degenerate axes.
`config.responsive: true`'s `ResizeObserver` doesn't reliably self-heal an initial 0x0 render across
browsers/Plotly versions the way it heals a live resize. The task's own testing session had no
browser/JS tooling available (pytest/ruff/curl only), so this exact class of bug shipped unflagged —
confirming CLAUDE.md's instruction to flag anything in web JS "that looks like it would fail at
runtime in an actual browser" is the right thing to actively hunt for, not a formality.

**How to apply:** for any future DOM-building JS in this repo (chart libraries, canvas, anything that
measures its container at init time), check the actual order of operations: does `appendChild` into
the live document tree happen *before* the library call that reads container dimensions, not after.
Reading top-to-bottom code order isn't enough — trace which variables are actually attached to
`document` at each call site, since intermediate containers (like `grid` here) can look attached
while still being off-DOM themselves.
