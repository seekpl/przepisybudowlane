import "server-only";

import { cookies } from "next/headers";

export const EDITOR_COOKIE = "pb_redakcja";

export async function editorToken(): Promise<string | null> {
  return (await cookies()).get(EDITOR_COOKIE)?.value ?? null;
}
