# Run it — gateway stub (Plan P2)

**Status:** stub only. Measure it (Plan P1) is closed. No gateway code until a design note exists, the same way WP0 came before the eval scripts.

| | |
|--|--|
| **Maps to** | Personal plan **Project 2 · Run it**. |
| **Not this phase** | Research agent / red-team (plan P3). New RAG features. |
| **Goal** | SEC GraphRAG model calls go through one gateway: it can fail closed, skip a repeat call, and survive a chaos demo. |

## Words this file uses

**Gateway.** One front door for model calls. Extract, route, answer, and judge ask the gateway. They do not each call the model on their own. A limit, a saved answer, or a failure rule then lives in one place.

**Call site.** A spot in the code that spends a model call. Extract turns filings into graph rows. Route picks graph, vectors, or both. Answer writes the reply. Judge scores that reply.

**Circuit breaker.** Same idea as the breaker in an apartment. If the model starts failing, the breaker opens and the next calls stop going out for a while. They get a fast failure instead of hanging on a dead API. Closed means calls go through.

**Fail closed.** When the call fails, or the breaker is open, the system returns the failure. It does not invent an answer so the demo still looks fine. What the caller actually receives is still a design-note decision. This file only names the rule.

**Semantic cache.** Save a model result and reuse it when a later request means the same thing. Semantic means the match can be by meaning, so two wordings of one question can hit one saved result. An exact cache only hits when the text is character for character the same.

**Cache key.** The fields that decide "this is the same request." The question text is not enough. The same words about a different ticker, or the same words with a different pile of evidence, are a different answer.

**Chaos demo.** Break something on purpose, usually the model call, and show the breaker and the cache doing the thing the design note promised. "Still works" gets written in that note before the demo exists.

**Design note.** The short writeup that comes before code, same role as WP0 on Measure it. It picks which call goes first, what opens the breaker, the cache key, and what the chaos demo breaks.

**Stub.** This file names those pieces. It does not pick a library, a port, or a new service. That choice waits for the design note.

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
