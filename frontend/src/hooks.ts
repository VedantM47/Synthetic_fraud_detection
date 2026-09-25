import { useCallback, useEffect, useRef, useState } from "react";
import { api, jobStreamUrl, type Job } from "./api";

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/** Fetch data whenever ``deps`` change. Keeps the previous data while reloading. */
export function useApi<T>(load: () => Promise<T>, deps: unknown[]): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loadRef
      .current()
      .then((value) => {
        if (!cancelled) {
          setData(value);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { data, error, loading, reload };
}

/**
 * Live job progress. Uses Server-Sent Events and falls back to polling if the
 * stream is unavailable (for example behind a proxy that buffers responses).
 */
export function useJobStream(jobId: string | null, onFinish?: (job: Job) => void): Job | null {
  const [job, setJob] = useState<Job | null>(null);
  const finishRef = useRef(onFinish);
  finishRef.current = onFinish;

  useEffect(() => {
    setJob(null);
    if (!jobId) return;
    let closed = false;
    let pollTimer: number | undefined;
    let finished = false;

    const handle = (next: Job) => {
      if (closed) return;
      setJob(next);
      if ((next.status === "completed" || next.status === "failed") && !finished) {
        finished = true;
        finishRef.current?.(next);
      }
    };

    const poll = () => {
      api
        .job(jobId)
        .then((next) => {
          handle(next);
          if (!closed && next.status !== "completed" && next.status !== "failed") {
            pollTimer = window.setTimeout(poll, 1000);
          }
        })
        .catch(() => {
          if (!closed) pollTimer = window.setTimeout(poll, 2000);
        });
    };

    let source: EventSource | null = null;
    if (typeof EventSource !== "undefined") {
      source = new EventSource(jobStreamUrl(jobId));
      source.onmessage = (event) => {
        try {
          const next = JSON.parse(event.data) as Job;
          handle(next);
          if (next.status === "completed" || next.status === "failed") source?.close();
        } catch {
          // ignore malformed frames
        }
      };
      source.onerror = () => {
        source?.close();
        source = null;
        if (!closed && !finished) poll();
      };
    } else {
      poll();
    }

    return () => {
      closed = true;
      source?.close();
      if (pollTimer) window.clearTimeout(pollTimer);
    };
  }, [jobId]);

  return job;
}

export type Theme = "light" | "dark" | "system";

function systemDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

export function useTheme(): { theme: Theme; resolved: "light" | "dark"; setTheme: (theme: Theme) => void } {
  const [theme, setThemeState] = useState<Theme>(() => {
    try {
      const saved = localStorage.getItem("theme");
      if (saved === "light" || saved === "dark") return saved;
    } catch {
      // storage can be unavailable
    }
    return "system";
  });
  const [osDark, setOsDark] = useState(systemDark());

  useEffect(() => {
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!query) return;
    const listener = () => setOsDark(query.matches);
    query.addEventListener("change", listener);
    return () => query.removeEventListener("change", listener);
  }, []);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    try {
      if (next === "system") localStorage.removeItem("theme");
      else localStorage.setItem("theme", next);
    } catch {
      // ignore
    }
    if (next === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = next;
  }, []);

  const resolved = theme === "system" ? (osDark ? "dark" : "light") : theme;
  return { theme, resolved, setTheme };
}

/** Read a CSS custom property (used to theme canvas-drawn graphs). */
export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
