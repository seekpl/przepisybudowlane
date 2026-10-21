import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const CARD = "/przepis/warunki-techniczne-par-12-ust-1";

/** Pozycja elementu w kolejności dokumentu — do sprawdzania, co stoi przed czym. */
async function docIndex(page: Page, selector: string): Promise<number> {
  return page.evaluate((sel) => {
    const all = Array.from(document.querySelectorAll("*"));
    const el = document.querySelector(sel);
    return el ? all.indexOf(el) : -1;
  }, selector);
}

async function setMode(page: Page, mode: "Prosty" | "Ekspercki") {
  const isMobile = (page.viewportSize()?.width ?? 1280) < 768;
  if (isMobile) await page.locator("summary").filter({ hasText: "Menu" }).click();
  const scope = isMobile ? page.locator(".pb-menu-panel") : page.locator(".pb-desktop-only").first();
  await scope.getByRole("button", { name: mode }).click();
  await expect(page.locator("body")).toHaveClass(mode === "Ekspercki" ? /pb-expert-page/ : /pb-simple-page/);
}

test("strona startowa prowadzi do wyszukiwarki z jawnymi synonimami", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Przepisy budowlane w jednym miejscu");
  await page.getByLabel("Czego szukasz?").fill("płot przy granicy");
  await page.getByRole("button", { name: "Szukaj" }).first().click();
  await expect(page).toHaveURL(/\/szukaj\?q=/);
  await expect(page.getByText("Szukamy też: ogrodzenie (dla „płot”).")).toBeVisible();
  await expect(page.getByRole("link", { name: "Odległość budynku od granicy działki" })).toBeVisible();
});

test("komunikat o aktualności stoi przed tekstem przepisu w obu trybach", async ({ page }) => {
  await page.goto(CARD);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Odległość budynku od granicy działki");
  // Typ i obowiązywanie z metadanych ELI (nagranie z 21.10.2026): t.j. aktu uznanego za uchylony.
  await expect(page.locator(".pb-card .pb-status-niepotwierdzona")).toContainText("Nie potwierdzono aktualności");
  await expect(page.locator(".pb-card .pb-type-jednolity")).toContainText("Tekst jednolity");
  await expect(page.locator(".pb-card .pb-notice").first()).toContainText("Ten akt nie obowiązuje od 21");
  // Tryb prosty: komunikat → objaśnienie → oficjalne brzmienie → metryka.
  const simple = await Promise.all([".pb-card .pb-notice", ".pb-card .pb-explain", ".pb-card .pb-law", ".pb-card .pb-cite"].map((s) => docIndex(page, s)));
  expect(simple).toEqual([...simple].sort((a, b) => a - b));
  await expect(page.locator(".pb-card .pb-explain")).toContainText("Objaśnienie nieurzędowe");
  await expect(page.locator(".pb-card .pb-explain")).toContainText("Treść demonstracyjna");

  await setMode(page, "Ekspercki");
  // Tryb ekspercki: komunikat → metryka → tekst → objaśnienie.
  const expert = await Promise.all([".pb-card .pb-notice", ".pb-card .pb-cite", ".pb-card .pb-law", ".pb-card .pb-explain"].map((s) => docIndex(page, s)));
  expect(expert).toEqual([...expert].sort((a, b) => a - b));
  await page.reload();
  await expect(page.locator("body")).toHaveClass(/pb-expert-page/);
  await setMode(page, "Prosty");
});

test("tekst z ELI tylko w PDF czeka na kontrolę człowieka i nie jest pokazywany", async ({ page }) => {
  await page.goto("/przepis/prawo-budowlane-art-29-ust-1-pkt-1a");
  await expect(page.locator(".pb-card .pb-status-niepotwierdzona")).toBeVisible();
  await expect(page.getByText("Tekst urzędowy czeka na sprawdzenie")).toBeVisible();
  // Brak brzmienia: ani tekstu, ani odznaki typu — tylko metryka z linkiem do oficjalnego tekstu.
  await expect(page.locator(".pb-card .pb-law")).toHaveCount(0);
  await expect(page.locator(".pb-card [class*='pb-type-']")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Otwórz oficjalny tekst" })).toHaveAttribute("href", "https://eli.gov.pl/eli/DU/2026/524");
  await expect(page.locator(".pb-status-potwierdzona")).toHaveCount(0);
});

test("kopiuj cytat kopiuje akt, publikator i jednostkę", async ({ page, context, browserName }) => {
  test.skip(browserName !== "chromium");
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto(CARD);
  await page.getByRole("button", { name: "Kopiuj cytat" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Cytat skopiowany do schowka" })).toBeAttached();
  const text = await page.evaluate(() => navigator.clipboard.readText());
  expect(text).toContain("Dz.U. 2022 poz. 1225, § 12 ust. 1");
});

test("kreator: bez odpowiedzi pokazuje komunikat, potem wynik z podstawą, odpowiedzi przetrwają odświeżenie", async ({ page }) => {
  await page.goto("/kreator/pozwolenie-zgloszenie");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.getByText("Krok 1 z 6")).toBeVisible();
  await page.getByRole("button", { name: "Dalej" }).click();
  await expect(page.locator(".pb-wizard").getByRole("alert")).toHaveText("Wybierz jedną odpowiedź, żeby przejść dalej.");
  for (const label of ["Wolno stojący dom jednorodzinny", "do 70 m²", "Jedną albo dwie", "Tak", "Tak"]) {
    await page.getByLabel(label, { exact: true }).check();
    await page.getByRole("button", { name: "Dalej" }).click();
  }
  await expect(page.getByRole("heading", { name: "Wystarczy zgłoszenie budowy" })).toBeVisible();
  await expect(page.getByText("Prawo budowlane, art. 29 ust. 1 pkt 1a · Dz.U. 2026 poz. 524")).toBeVisible();
  await expect(page.locator(".pb-result .pb-status-niepotwierdzona")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Wystarczy zgłoszenie budowy" })).toBeVisible();
  await page.getByRole("button", { name: "Zmień odpowiedzi" }).click();
  await expect(page.getByText("Krok 1 z 6")).toBeVisible();
  await expect(page.getByLabel("Wolno stojący dom jednorodzinny")).toBeChecked();
});

test("kreator: przypadek poza zakresem mówi to wprost", async ({ page }) => {
  await page.goto("/kreator/pozwolenie-zgloszenie");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.getByLabel("Ogrodzenie").check();
  await page.getByRole("button", { name: "Dalej" }).click();
  await expect(page.getByRole("heading", { name: "Tego przypadku kreator jeszcze nie obejmuje" })).toBeVisible();
});

test("zgłoś błąd: walidacja i numer zgłoszenia z terminem", async ({ page }) => {
  await page.goto(CARD);
  const form = page.locator("section", { has: page.getByRole("heading", { name: "Zgłoś błąd" }) });
  await form.getByRole("button", { name: "Wyślij zgłoszenie" }).click();
  await expect(form.getByRole("alert")).toContainText("Opisz krótko");
  await form.getByLabel("Co jest nie tak?").fill("W karcie brakuje ust. 2 o sytuowaniu przy granicy.");
  await form.getByRole("button", { name: "Wyślij zgłoszenie" }).click();
  await expect(form.getByRole("status")).toContainText(/Zgłoszenie ma numer ZB-\d+\. Sprawdzimy je do \d{1,2}\.\d{2}\.\d{4}\./);
});

test("trwały adres wersji przepisu", async ({ page }) => {
  await page.goto(CARD);
  const href = await page.getByRole("link", { name: "Adres tej wersji" }).getAttribute("href");
  expect(href).toMatch(/\/przepis\/warunki-techniczne-par-12-ust-1\/wersja\/\d+$/);
  await page.goto(href!);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Odległość budynku od granicy działki");
});

test("pierwszy Tab trafia w link „Przejdź do treści”", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Przejdź do treści" })).toBeFocused();
});

const PAGES = ["/", CARD, "/kreator/pozwolenie-zgloszenie", "/szukaj?q=dom", "/slowniczek", "/sciezki/budowa-domu", "/akty/prawo-budowlane", "/stan-danych", "/o-serwisie"];

for (const scheme of ["light", "dark"] as const) {
  test(`WCAG 2.1 AA (axe) — motyw ${scheme === "light" ? "jasny" : "ciemny"}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    for (const path of PAGES) {
      await page.goto(path);
      const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      const summary = result.violations.map((v) => `${path}: ${v.id} — ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
      expect(summary).toEqual([]);
    }
  });
}

test("bez przewijania w poziomie, także przy zwiększonych odstępach w tekście (WCAG 1.4.12)", async ({ page }) => {
  for (const path of PAGES) {
    await page.goto(path);
    await page.addStyleTag({
      content: "* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; } p { margin-bottom: 2em !important; }",
    });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
});

test("pola dotyku w trybie prostym mają co najmniej 44 px", async ({ page }) => {
  await page.goto("/kreator/pozwolenie-zgloszenie");
  for (const el of await page.locator(".pb-btn.pb-simple:visible, .pb-option:visible").all()) {
    const box = await el.boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(44);
  }
});
