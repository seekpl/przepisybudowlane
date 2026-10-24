"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";

import { editorialFetch, postReport } from "@/lib/api";
import { EDITOR_COOKIE } from "@/lib/editor";
import { MODE_COOKIE } from "@/lib/mode";

export async function setMode(formData: FormData): Promise<void> {
  const value = formData.get("tryb") === "ekspert" ? "ekspert" : "prosty";
  (await cookies()).set(MODE_COOKIE, value, { path: "/", maxAge: 60 * 60 * 24 * 365, sameSite: "lax", httpOnly: false });
  revalidatePath("/", "layout");
}

export interface ReportState {
  status: "idle" | "ok" | "error";
  message?: string;
  fields?: { message?: string; email?: string };
}

export async function submitReport(_prev: ReportState, formData: FormData): Promise<ReportState> {
  const message = String(formData.get("message") ?? "").trim();
  const email = String(formData.get("email") ?? "").trim();
  const consent = formData.get("consent") === "on";
  if (message.length < 5) {
    return { status: "error", message: "Opisz krótko, co jest nie tak — wystarczy jedno zdanie.", fields: { message, email } };
  }
  if (email && !consent) {
    return { status: "error", message: "Zaznacz zgodę na użycie adresu albo usuń adres z formularza.", fields: { message, email } };
  }
  const res = await postReport({
    target_path: String(formData.get("target_path") ?? "/"),
    target_label: String(formData.get("target_label") ?? "") || null,
    unit_slug: String(formData.get("unit_slug") ?? "") || null,
    message,
    contact_email: email || null,
    consent,
  });
  if (!res.ok) return { status: "error", message: res.error, fields: { message, email } };
  return { status: "ok", message: res.message };
}

// --- Redakcja (token do czasu OIDC; trzymany w ciasteczku httpOnly) ---------------------------

export interface EditorState {
  error?: string;
  ok?: string;
}

async function token(): Promise<string> {
  return (await cookies()).get(EDITOR_COOKIE)?.value ?? "";
}

export async function editorLogin(_prev: EditorState, formData: FormData): Promise<EditorState> {
  const value = String(formData.get("token") ?? "").trim();
  try {
    await editorialFetch(value, "/ja");
  } catch {
    return { error: "Ten token nie pasuje do żadnej osoby z redakcji. Sprawdź go i spróbuj jeszcze raz." };
  }
  (await cookies()).set(EDITOR_COOKIE, value, { path: "/redakcja", httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production", maxAge: 60 * 60 * 8 });
  revalidatePath("/redakcja");
  return {};
}

export async function editorLogout(): Promise<void> {
  (await cookies()).delete({ name: EDITOR_COOKIE, path: "/redakcja" });
  revalidatePath("/redakcja");
}

export async function editorTransition(_prev: EditorState, formData: FormData): Promise<EditorState> {
  const entity = String(formData.get("entity"));
  const id = String(formData.get("item_id"));
  const to = String(formData.get("to_state"));
  const comment = String(formData.get("comment") ?? "").trim() || null;
  try {
    await editorialFetch(await token(), `/tresci/${encodeURIComponent(entity)}/${encodeURIComponent(id)}/przejscie`, {
      method: "POST",
      body: JSON.stringify({ to_state: to, comment }),
    });
  } catch (e) {
    return { error: e instanceof Error ? e.message : "Nie udało się zmienić stanu." };
  }
  revalidatePath("/redakcja");
  return { ok: "Zapisano." };
}

export async function editorCloseTask(_prev: EditorState, formData: FormData): Promise<EditorState> {
  const id = String(formData.get("item_id"));
  const resolution = String(formData.get("resolution") ?? "").trim();
  if (resolution.length < 3) return { error: "Opisz krótko, jak rozwiązano zadanie." };
  try {
    await editorialFetch(await token(), `/zadania/${encodeURIComponent(id)}/zamknij`, {
      method: "POST",
      body: JSON.stringify({ resolution }),
    });
  } catch (e) {
    return { error: e instanceof Error ? e.message : "Nie udało się zamknąć zadania." };
  }
  revalidatePath("/redakcja");
  return { ok: "Zadanie zamknięte." };
}

export async function editorDecideText(_prev: EditorState, formData: FormData): Promise<EditorState> {
  const id = String(formData.get("item_id"));
  const accept = formData.get("decision") === "akceptuj";
  const comment = String(formData.get("comment") ?? "").trim();
  if (comment.length < 3) return { error: "Uzasadnij decyzję jednym zdaniem." };
  try {
    await editorialFetch(await token(), `/teksty/${encodeURIComponent(id)}/decyzja`, {
      method: "POST",
      body: JSON.stringify({ accept, comment }),
    });
  } catch (e) {
    return { error: e instanceof Error ? e.message : "Nie udało się zapisać decyzji." };
  }
  revalidatePath("/redakcja");
  return { ok: "Decyzja zapisana." };
}

export async function editorCloseAlarm(_prev: EditorState, formData: FormData): Promise<EditorState> {
  const id = String(formData.get("item_id"));
  const resolution = String(formData.get("resolution") ?? "").trim();
  if (resolution.length < 3) return { error: "Opisz, co sprawdzono i dlaczego można wznowić synchronizację." };
  try {
    await editorialFetch(await token(), `/alarmy/${encodeURIComponent(id)}/zamknij`, {
      method: "POST",
      body: JSON.stringify({ resolution }),
    });
  } catch (e) {
    return { error: e instanceof Error ? e.message : "Nie udało się zamknąć alarmu." };
  }
  revalidatePath("/redakcja");
  return { ok: "Alarm zamknięty — następny przebieg synchronizacji ruszy normalnie." };
}

export async function editorTransitional(_prev: EditorState, formData: FormData): Promise<EditorState> {
  const slug = String(formData.get("act_slug") ?? "");
  const field = (name: string) => String(formData.get(name) ?? "").trim();
  if (!field("valid_from")) return { error: "Podaj datę, od której akt stosuje się przejściowo." };
  if (field("basis").length < 3) return { error: "Wskaż przepis przejściowy, na którym opierasz decyzję." };
  if (field("description").length < 10) return { error: "Opisz w jednym–dwóch zdaniach, do jakich spraw akt stosuje się dalej." };
  try {
    await editorialFetch(await token(), `/akty/${encodeURIComponent(slug)}/stosowanie-przejsciowe`, {
      method: "POST",
      body: JSON.stringify({
        valid_from: field("valid_from"),
        valid_to: field("valid_to") || null,
        basis: field("basis"),
        title: field("title") || null,
        description: field("description"),
        task_id: Number(formData.get("task_id")) || null,
      }),
    });
  } catch (e) {
    return { error: e instanceof Error ? e.message : "Nie udało się zapisać decyzji." };
  }
  revalidatePath("/redakcja");
  return { ok: "Zapisano — karty aktu pokażą stosowanie przejściowe z tą podstawą." };
}

export async function editorAddSynonym(_prev: EditorState, formData: FormData): Promise<EditorState> {
  const term = String(formData.get("term") ?? "").trim();
  const expansions = String(formData.get("expansions") ?? "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
  if (expansions.length === 0) return { error: "Wpisz słowa, których ma szukać wyszukiwarka, oddzielone przecinkami." };
  try {
    await editorialFetch(await token(), "/synonimy", {
      method: "POST",
      body: JSON.stringify({ term, expansions, miss_id: Number(formData.get("miss_id")) || null }),
    });
  } catch (e) {
    return { error: e instanceof Error ? e.message : "Nie udało się dodać synonimu." };
  }
  revalidatePath("/redakcja");
  return { ok: `Dodano: „${term}” → ${expansions.join(", ")}.` };
}

export async function editorDismissMiss(formData: FormData): Promise<void> {
  await editorialFetch(await token(), `/propozycje-synonimow/${encodeURIComponent(String(formData.get("miss_id")))}/odrzuc`, {
    method: "POST",
  });
  revalidatePath("/redakcja");
}

export async function editorDecideRule(formData: FormData): Promise<void> {
  await editorialFetch(await token(), `/reguly-kreatora/${encodeURIComponent(String(formData.get("rule_id")))}/decyzja`, {
    method: "POST",
    body: JSON.stringify({ accept: formData.get("decision") === "zatwierdz" }),
  });
  revalidatePath("/redakcja");
}

/** Szkic AI: zatwierdzenie publikuje objaśnienie z nazwiskiem recenzenta, odrzucenie zwraca je do szkiców (3.6). */
export async function editorDecideAiDraft(_prev: EditorState, formData: FormData): Promise<EditorState> {
  const id = String(formData.get("item_id"));
  const accept = formData.get("decision") === "zatwierdz";
  const comment = String(formData.get("comment") ?? "").trim();
  if (comment.length < 3) return { error: "Napisz jednym zdaniem, co sprawdzono — decyzja jest podpisana Twoim nazwiskiem." };
  try {
    await editorialFetch(await token(), `/szkice-ai/${encodeURIComponent(id)}/decyzja`, {
      method: "POST",
      body: JSON.stringify({ accept, comment }),
    });
  } catch (e) {
    return { error: e instanceof Error ? e.message : "Nie udało się zapisać decyzji." };
  }
  revalidatePath("/redakcja");
  return { ok: accept ? "Objaśnienie opublikowane." : "Szkic odrzucony." };
}

export async function editorRequestAiDraft(_prev: EditorState, formData: FormData): Promise<EditorState> {
  const raw = String(formData.get("unit") ?? "").trim();
  const slug = raw.replace(/^.*\/przepis\//, "").replace(/[?#].*$/, "");
  if (!slug) return { error: "Wklej adres karty przepisu, np. /przepis/prawo-budowlane-art-29-ust-1-pkt-2." };
  try {
    await editorialFetch(await token(), "/szkice-ai", { method: "POST", body: JSON.stringify({ unit_slug: slug }) });
  } catch (e) {
    return { error: e instanceof Error ? e.message : "Nie udało się zlecić szkicu." };
  }
  revalidatePath("/redakcja");
  return { ok: "Zlecono — szkic pojawi się w kolejce po najbliższym przebiegu workera." };
}
