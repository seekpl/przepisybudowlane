import "server-only";

import { cookies } from "next/headers";

import type { Mode } from "./types";

export const MODE_COOKIE = "pb_tryb";

/** Tryb prosty jest domyślny; ekspercki wybiera użytkownik (ciasteczko funkcjonalne, bez danych osobowych). */
export async function getMode(): Promise<Mode> {
  const value = (await cookies()).get(MODE_COOKIE)?.value;
  return value === "ekspert" ? "expert" : "simple";
}
