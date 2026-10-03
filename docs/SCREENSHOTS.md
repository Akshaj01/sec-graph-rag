# Screenshots for the README

Recruiters skim visuals. Add two images, then uncomment the image block in `README.md`.

## 1. `docs/images/neo4j-graph.png`

1. `docker compose up -d`
2. Open http://localhost:7474 — login `neo4j` / `password`
3. Run:

```cypher
MATCH (c:Company {home_ticker:'AAPL'})-[r:PRODUCES_PRODUCT]->(p)
RETURN c, r, p
LIMIT 25
```

4. Zoom so company + a handful of products are readable → screenshot → save as `docs/images/neo4j-graph.png`

Optional second query for risks:

```cypher
MATCH (c:Company {home_ticker:'AAPL'})-[r:EXPOSED_TO_RISK]->(x)
RETURN c, r, x
LIMIT 15
```

## 2. `docs/images/ask-api.png`

1. Start API: `python -m uvicorn api:app --host 127.0.0.1 --port 8000`
2. Open http://127.0.0.1:8000/docs
3. `POST /ask` with:

```json
{
  "question": "What product lines does Apple produce?",
  "ticker": "AAPL"
}
```

4. Expand the response so `summary`, `route_effective`, `citations_valid`, and a couple of `claims` / chunk ids are visible → screenshot → `docs/images/ask-api.png`

## 3. Uncomment README images

In `README.md`, remove the HTML comment wrappers around the `<img>` block under **Architecture**.

## Optional

- 30–60s Loom: ask one graph question + one vector question, show citations. Link from README.
- Do **not** commit `.env` or the PDF under `resume/` (gitignored).
