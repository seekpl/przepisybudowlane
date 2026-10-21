import "server-only";

import type {
  Act,
  DataStatus,
  Definition,
  GlossaryTerm,
  Guide,
  GuideSummary,
  Home,
  Provision,
  SearchResult,
  Synonym,
  Tree,
} from "./types";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

// Bez pamięci podręcznej: status aktualności liczymy przy każdym żądaniu — stary wynik mógłby udawać świeżość.
async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BACKEND}/api/v1${path}`, { cache: "no-store", headers: { Accept: "application/json" } });
  if (!res.ok) throw new ApiError(`API ${path}: HTTP ${res.status}`, res.status);
  return (await res.json()) as T;
}

/** Zwraca null, gdy zasobu nie ma (404) — strona pokaże wtedy notFound(). */
async function getOrNull<T>(path: string): Promise<T | null> {
  try {
    return await get<T>(path);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

const q = encodeURIComponent;

export const api = {
  home: () => get<Home>("/start"),
  provision: (slug: string, explanationId?: number) =>
    getOrNull<Provision>(`/przepisy/${q(slug)}${explanationId ? `?objasnienie=${explanationId}` : ""}`),
  provisionVersion: (slug: string, versionId: number) =>
    getOrNull<Provision>(`/przepisy/${q(slug)}/wersje/${versionId}`),
  acts: () => get<Act[]>("/akty"),
  act: (slug: string) => getOrNull<Act>(`/akty/${q(slug)}`),
  search: (query: string) => get<SearchResult>(`/szukaj?q=${q(query)}`),
  synonyms: () => get<Synonym[]>("/synonimy"),
  glossary: () => get<GlossaryTerm[]>("/slowniczek"),
  definitions: () => get<Definition[]>("/definicje"),
  guides: () => get<GuideSummary[]>("/sciezki"),
  guide: (slug: string) => getOrNull<Guide>(`/sciezki/${q(slug)}`),
  tree: (slug: string) => getOrNull<Tree>(`/kreatory/${q(slug)}`),
  status: () => get<DataStatus>("/stan"),
};

export async function postReport(body: unknown): Promise<{ ok: true; number: string; message: string } | { ok: false; error: string }> {
  const res = await fetch(`${BACKEND}/api/v1/zgloszenia`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown; number?: string; message?: string };
  if (res.ok) return { ok: true, number: data.number ?? "", message: data.message ?? "" };
  const detail = typeof data.detail === "string" ? data.detail : "Sprawdź pola formularza i spróbuj jeszcze raz.";
  return { ok: false, error: detail };
}

export async function editorialFetch<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND}/api/v1/redakcja${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  const data = (await res.json().catch(() => ({}))) as T & { detail?: string };
  if (!res.ok) throw new ApiError(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`, res.status);
  return data;
}
