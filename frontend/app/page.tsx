import Link from "next/link";

import { Icon } from "@/components/ds/Icon";
import { ProvisionItem } from "@/components/site/ProvisionItem";
import { SearchForm } from "@/components/site/SearchForm";
import { api } from "@/lib/api";
import { dateTime, typo } from "@/lib/format";
import { getMode } from "@/lib/mode";

export default async function HomePage() {
  const [home, mode] = await Promise.all([api.home(), getMode()]);
  const tree = home.trees[0];
  return (
    <>
      <section className="pb-page-head" aria-labelledby="start-tytul">
        <h1 id="start-tytul" className="ui-display">
          Przepisy budowlane w jednym miejscu
        </h1>
        <p className="ui-body">
          {typo(
            "Oficjalny tekst, data, na którą jest aktualny, i objaśnienie prostym językiem. Zawsze z linkiem do Dziennika Ustaw.",
          )}
        </p>
      </section>

      <SearchForm mode={mode} />
      <p className="ui-small pb-muted" style={{ marginTop: "var(--space-2)" }}>
        Na przykład: <Link href="/szukaj?q=odległość od granicy">odległość od granicy</Link>,{" "}
        <Link href="/szukaj?q=płot">płot</Link>, <Link href="/szukaj?q=warunki zabudowy">warunki zabudowy</Link>
      </p>

      <section className="pb-section" aria-labelledby="start-pytania" style={{ marginTop: "var(--space-7)" }}>
        <h2 id="start-pytania" className="ui-title">
          Zacznij od pytania
        </h2>
        <ul className="pb-grid pb-grid-3 pb-plain-list">
          {tree ? (
            <li>
              <Link href={tree.url} className="pb-tile">
                <span className="pb-tile-title ui-heading">
                  <Icon name="list-tree" size={20} />
                  {tree.title}
                </span>
                <span className="ui-body">Kilka pytań i odpowiedź z podstawą prawną: pozwolenie, zgłoszenie czy nic.</span>
                <span className="pb-tile-more ui-small">
                  Przejdź do kreatora <Icon name="arrow-right" />
                </span>
              </Link>
            </li>
          ) : null}
          <li>
            <Link href="/sciezki" className="pb-tile">
              <span className="pb-tile-title ui-heading">
                <Icon name="list-checks" size={20} />
                Krok po kroku
              </span>
              <span className="ui-body">
                {typo(`Budowa domu, zakończenie budowy, zakup działki — ${home.guides.length} ścieżki z dokumentami i urzędami.`)}
              </span>
              <span className="pb-tile-more ui-small">
                Zobacz ścieżki <Icon name="arrow-right" />
              </span>
            </Link>
          </li>
          <li>
            <Link href="/slowniczek" className="pb-tile">
              <span className="pb-tile-title ui-heading">
                <Icon name="book-open" size={20} />
                Słowniczek
              </span>
              <span className="ui-body">
                {typo(`${home.glossary_count} pojęć z ustaw wyjaśnionych prostym językiem, z podstawą prawną.`)}
              </span>
              <span className="pb-tile-more ui-small">
                Otwórz słowniczek <Icon name="arrow-right" />
              </span>
            </Link>
          </li>
        </ul>
      </section>

      <section className="pb-section" aria-labelledby="start-przepisy">
        <h2 id="start-przepisy" className="ui-title">
          Często sprawdzane przepisy
        </h2>
        <ul className="pb-list">
          {home.featured.map((p) => (
            <ProvisionItem key={p.slug} p={p} />
          ))}
        </ul>
      </section>

      <section className="pb-section pb-panel pb-panel-sunken" aria-labelledby="start-stan">
        <h2 id="start-stan" className="ui-heading">
          Skąd wiemy, że przepis jest aktualny
        </h2>
        <p className="ui-body pb-measure">
          {typo(
            "Tekst pobieramy z oficjalnego ELI API Kancelarii Sejmu i oznaczamy jego typ. Jeśli synchronizacja się spóźnia, karta mówi to wprost — nie udajemy świeżości.",
          )}
        </p>
        <p className="ui-small" style={{ marginTop: "var(--space-2)" }}>
          Ostatnia udana synchronizacja:{" "}
          <span className="meta-small">{home.status.last_success_at ? dateTime(home.status.last_success_at) : "jeszcze nie było"}</span>
          . <Link href="/stan-danych">Stan danych</Link>
        </p>
      </section>
    </>
  );
}
