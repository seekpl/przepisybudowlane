import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="pb-footer">
      <div className="pb-wrap pb-footer-grid">
        <div className="pb-stack-2">
          <p className="ui-heading">Przepisy budowlane</p>
          <p className="ui-small pb-measure">
            Niezależny serwis informacyjny — nie jest serwisem państwowym. Oficjalnym źródłem prawa jest Dziennik Ustaw;
            każdy przepis prowadzi do aktu w Dzienniku Ustaw. Objaśnienia to informacja, nie porada prawna.
          </p>
          <p className="ui-small pb-muted">Nazwa robocza. Operator usługi: do wskazania.</p>
        </div>
        <nav aria-label="Informacje o serwisie">
          <ul className="ui-small">
            <li>
              <Link href="/o-serwisie">O serwisie i zasadach</Link>
            </li>
            <li>
              <Link href="/stan-danych">Stan danych i synchronizacji</Link>
            </li>
            <li>
              <Link href="/o-serwisie#synonimy">Słownik synonimów wyszukiwarki</Link>
            </li>
            <li>
              <a href="/api/v1/przepisy">Publiczne API (JSON)</a>
            </li>
            <li>
              <Link href="/redakcja">Panel redakcji</Link>
            </li>
          </ul>
        </nav>
      </div>
    </footer>
  );
}
