# Run it — gateway stub (Plan P2)

**Status:** stub only. Measure it (Plan P1) is closed. No gateway code until a design note exists, the same way WP0 came before the eval scripts.

| | |
|--|--|
| **Maps to** | Personal plan **Project 2 · Run it**. |
| **Not this phase** | Research agent / red-team (plan P3). New RAG features. |
| **Goal** | SEC GraphRAG model calls go through one gateway: it can fail closed, skip a repeat call, and survive a chaos demo. |

---

## Already named (do not add pieces yet)

1. **Circuit breakers** on the model calls.
2. **Semantic cache** so a repeated question does not pay for another call.
3. **Chaos demo** that shows the breaker and the cache under failure.
4. **Point the existing calls through it** once those three exist. Call sites today: extract, route, answer, judge.

## Write before any code

- Which call is first (answer is the one a user hits; extract is the expensive one).
- What opens the breaker, and what the caller receives when it is open.
- The cache key. A question alone is not enough if the ticker or the evidence pack differs.
- What the chaos demo breaks, and what “still works” means in that demo.

## Explicitly out of scope until this stub grows a design note

Libraries, ports, and a new service boundary. Those get chosen in the design note, not in this file.
