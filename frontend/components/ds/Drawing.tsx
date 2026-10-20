// Rysunki techniczne z identyfikacji (grupa „Rysunki”), osadzone inline, żeby w motywie ciemnym
// tusze brały kolory z tokenów (primary, ink-muted, accent, surface-raised). Każdy ma opis tekstowy.
// Wartości na rysunkach są przykładowe; rysunek stoi przy objaśnieniu, nigdy zamiast tekstu przepisu.

const DRAWINGS = {
  "rzut-odleglosc-od-granicy": {
    title: "Odległość budynku od granicy działki — rzut",
    desc: "Rzut działki z góry. Budynek stoi ścianą z oknami w stronę lewej granicy, w odległości 4 m od niej, i ścianą bez okien w stronę górnej granicy, w odległości 3 m.",
    body: (
      <>
        <rect className="bg" width="480" height="320" />
        <path className="g" d="M40 300V30h420" />
        <text className="s" x="46" y="22">granica działki</text>
        <rect className="b" x="120" y="90" width="200" height="150" />
        <rect className="w" x="116" y="120" width="8" height="28" /><rect className="w" x="116" y="182" width="8" height="28" />
        <path className="d" d="M40 165h80M40 159v12M120 159v12" />
        <text className="m" x="64" y="157">4 m</text>
        <path className="d" d="M260 30v60M254 30h12M254 90h12" />
        <text className="m" x="270" y="66">3 m</text>
        <text className="l" x="134" y="270">ściana z oknami → 4 m</text>
        <text className="l" x="134" y="290">ściana bez okien → 3 m</text>
        <text className="s" x="180" y="170">budynek</text>
      </>
    ),
  },
  "przekroj-wysokosc-budynku": {
    title: "Wysokość budynku — przekrój",
    desc: "Przekrój budynku z dachem dwuspadowym. Linia wymiarowa biegnie od poziomu terenu przy wejściu do najwyżej położonej krawędzi dachu i oznacza wysokość budynku.",
    body: (
      <>
        <rect className="bg" width="480" height="320" />
        <path className="t" d="M20 260h440" />
        <path className="t" d="M30 260l-8 10M60 260l-8 10M90 260l-8 10M120 260l-8 10M380 260l-8 10M410 260l-8 10M440 260l-8 10" />
        <text className="s" x="22" y="290">poziom terenu</text>
        <path className="b" d="M150 260V150l90-70 90 70v110z" />
        <path className="b" d="M150 150h180" />
        <rect className="w" x="226" y="214" width="28" height="46" />
        <path className="d" d="M380 260V80M374 260h12M374 80h12M246 80h140" />
        <path className="t" d="M246 80h0" />
        <text className="m" x="392" y="166">H</text>
        <text className="l" x="392" y="186">wysokość</text>
        <text className="l" x="392" y="202">budynku</text>
        <text className="s" x="160" y="72">najwyższa krawędź dachu</text>
      </>
    ),
  },
  "rzut-linia-zabudowy": {
    title: "Nieprzekraczalna linia zabudowy — rzut",
    desc: "Rzut działki przy drodze. Nieprzekraczalna linia zabudowy biegnie równolegle do frontowej granicy działki w odległości ustalonej w planie miejscowym, na przykład 6 m. Budynek stoi w całości za tą linią.",
    body: (
      <>
        <rect className="bg" width="480" height="320" />
        <path className="t" d="M20 290h440M20 262h440" />
        <text className="s" x="200" y="282">droga</text>
        <path className="g" d="M40 250V30h400v220z" />
        <text className="s" x="46" y="22">granica działki</text>
        <path className="b" d="M40 190h400" strokeDasharray="6 6" strokeWidth="2" />
        <text className="l" x="190" y="208">nieprzekraczalna linia zabudowy</text>
        <rect className="b" x="140" y="70" width="190" height="110" />
        <text className="s" x="210" y="130">budynek</text>
        <path className="d" d="M90 190v60M84 190h12M84 250h12" />
        <text className="m" x="100" y="226">np. 6 m</text>
      </>
    ),
  },
} as const;

export type DrawingName = keyof typeof DRAWINGS;

export function isDrawing(name: string | null | undefined): name is DrawingName {
  return !!name && name in DRAWINGS;
}

export function Drawing({ name, idSuffix = "" }: { name: DrawingName; idSuffix?: string }) {
  const id = `rys-${name}${idSuffix}`;
  const d = DRAWINGS[name];
  return (
    <figure className="pb-drawing">
      <svg viewBox="0 0 480 320" role="img" aria-labelledby={`${id}-t ${id}-d`}>
        <title id={`${id}-t`}>{d.title}</title>
        <desc id={`${id}-d`}>{d.desc}</desc>
        {d.body}
      </svg>
      <figcaption className="ui-small pb-muted">
        <span className="pb-drawing-title">{d.title}.</span> {d.desc} Wartości są przykładowe.
      </figcaption>
    </figure>
  );
}
