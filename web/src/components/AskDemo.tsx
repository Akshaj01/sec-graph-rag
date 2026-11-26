"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState } from "react";

import { TraceReveal } from "@/components/TraceReveal";
import { apiUrl, askQuestion } from "@/lib/api";
import { findSavedRun } from "@/lib/fixtures";
import { SAVED_RUNS_ONLY } from "@/lib/mode";
import { SAMPLES, TICKERS } from "@/lib/samples";
import type { AskResponse } from "@/lib/types";

type Mode = "live" | "saved";

// A saved-runs-only build lists only the samples it can play.
const VISIBLE_SAMPLES = SAVED_RUNS_ONLY
  ? SAMPLES.filter((sample) => findSavedRun(sample.question, sample.ticker))
  : SAMPLES;

type Shown = {
  id: number;
  response: AskResponse;
  saved: boolean;
  notice: string | null;
};

export function AskDemo() {
  const [mode, setMode] = useState<Mode>(SAVED_RUNS_ONLY ? "saved" : "live");
  const [ticker, setTicker] = useState<string>("AAPL");
  const [question, setQuestion] = useState("");
  const [shown, setShown] = useState<Shown | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const runCount = useRef(0);

  const mutation = useMutation({
    mutationFn: askQuestion,
  });

  function presentSaved(q: string, t: string, becauseLiveFailed: boolean): boolean {
    const run = findSavedRun(q, t);
    if (!run) return false;
    const id = runCount.current + 1;
    runCount.current = id;
    setShown({
      id,
      response: run.response,
      saved: true,
      notice: becauseLiveFailed
        ? "The local API did not answer. Showing the saved run for this question."
        : run.note,
    });
    return true;
  }

  function ask(nextQuestion: string, nextTicker: string) {
    const q = nextQuestion.trim();
    if (!q) return;
    setQuestion(q);
    setTicker(nextTicker);
    setShown(null);
    setNote(null);

    if (mode === "saved") {
      const found = presentSaved(q, nextTicker, false);
      if (!found) {
        setNote(
          SAVED_RUNS_ONLY
            ? "This hosted demo has no live API, and there is no saved run for this question. Saved runs cover Apple products, NVIDIA products and risks, and the Bitcoin refusal. Clone the repo to ask your own."
            : "No saved run for this question. Saved runs cover Apple products, NVIDIA products and risks, and the Bitcoin refusal.",
        );
      }
      return;
    }

    mutation.mutate(
      { question: q, ticker: nextTicker },
      {
        onSuccess: (response) => {
          const id = runCount.current + 1;
          runCount.current = id;
          setShown({ id, response, saved: false, notice: null });
        },
        onError: () => {
          const found = presentSaved(q, nextTicker, true);
          if (!found) {
            setNote(
              `The local API at ${apiUrl()} did not answer, and there is no saved run for this question.`,
            );
          }
        },
      },
    );
  }

  return (
    <div>
      <h1 className="font-serif text-4xl leading-tight tracking-tight sm:text-5xl">
        Ask a 10-K.
      </h1>
      <p className="mt-4 max-w-[42rem] text-lg leading-relaxed">
        Follow the route, the edges, the passages, and the chunks this answer
        is allowed to cite.
      </p>

      <div className="mt-8 flex flex-wrap gap-2" role="group" aria-label="Issuer">
        {TICKERS.map((item) => {
          const selected = item === ticker;
          return (
            <button
              key={item}
              type="button"
              aria-pressed={selected}
              onClick={() => setTicker(item)}
              className={
                selected
                  ? "border-b-2 border-pine px-1 py-1 text-sm text-ink"
                  : "border-b-2 border-transparent px-1 py-1 text-sm text-slate"
              }
            >
              {item}
            </button>
          );
        })}
      </div>

      <form
        className="mt-6"
        onSubmit={(event) => {
          event.preventDefault();
          ask(question, ticker);
        }}
      >
        <label htmlFor="question" className="text-sm text-slate">
          Question about {ticker}
        </label>
        <textarea
          id="question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={3}
          required
          placeholder="What product lines does Apple produce?"
          className="mt-2 w-full resize-y border border-rule bg-sheet px-4 py-4 font-serif text-2xl leading-snug"
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={mutation.isPending || question.trim().length === 0}
            className="border border-ink bg-ink px-4 py-2 text-sheet disabled:cursor-wait disabled:opacity-60"
          >
            {mutation.isPending ? "Asking…" : "Ask"}
          </button>
          {!SAVED_RUNS_ONLY && (
            <div role="group" aria-label="Where the answer comes from">
              <button
                type="button"
                aria-pressed={mode === "live"}
                onClick={() => setMode("live")}
                className={
                  mode === "live"
                    ? "border-b-2 border-pine px-1 py-2 text-sm text-ink"
                    : "border-b-2 border-transparent px-1 py-2 text-sm text-slate"
                }
              >
                Live API
              </button>
              <button
                type="button"
                aria-pressed={mode === "saved"}
                onClick={() => setMode("saved")}
                className={
                  mode === "saved"
                    ? "border-b-2 border-pine px-1 py-2 text-sm text-ink"
                    : "border-b-2 border-transparent px-1 py-2 text-sm text-slate"
                }
              >
                Saved runs
              </button>
            </div>
          )}
        </div>
      </form>

      <p className="mt-4 max-w-[42rem] text-sm text-slate">
        {SAVED_RUNS_ONLY
          ? "This hosted demo plays saved runs: real POST /ask responses, stored. It never calls the model. Clone the repo and run the API to ask your own questions."
          : mode === "live"
            ? "A live question calls the local API, which calls the model. If that API is down, a matching saved run is shown instead."
            : "Saved runs are stored responses. They do not call the model."}
      </p>

      <div className="mt-6 flex flex-col items-start gap-2">
        {VISIBLE_SAMPLES.map((sample) => (
          <button
            key={sample.id}
            type="button"
            onClick={() => ask(sample.question, sample.ticker)}
            disabled={mutation.isPending}
            className="text-left text-ink underline decoration-rule underline-offset-4 hover:decoration-pine disabled:opacity-60"
          >
            {sample.label}
            <span className="ml-2 text-slate">{sample.ticker}</span>
          </button>
        ))}
        <Link
          href="/results#side-by-side"
          className="mt-2 text-sm text-pine underline decoration-rule underline-offset-4 hover:decoration-pine"
        >
          Hybrid and vector-only, side by side →
        </Link>
      </div>

      <div aria-live="polite">
        {mutation.isPending && (
          <p className="mt-8 max-w-[42rem]">
            Asking the local API. The route, the filings, and the answer come
            back together, then appear in order.
          </p>
        )}
        {note && !mutation.isPending && (
          <p className="mt-8 max-w-[42rem] text-stamp">{note}</p>
        )}
        {shown && !mutation.isPending && (
          <TraceReveal
            key={shown.id}
            response={shown.response}
            saved={shown.saved}
            notice={shown.notice}
          />
        )}
      </div>
    </div>
  );
}
