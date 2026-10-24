// Typy odpowiedzi publicznego API (backend/app/api/schemas.py).

export type Mode = "simple" | "expert";
export type FreshnessStatus = "potwierdzona" | "zmiana" | "przejsciowa" | "niepotwierdzona" | "zawieszona";
export type TextType = "ogloszony" | "jednolity" | "kompilacja" | "nierozpoznany";

export interface Paragraph {
  unit: string;
  text: string;
}

export interface Notice {
  status: FreshnessStatus;
  code: string;
  title: string;
  body: string;
}

export interface Freshness {
  status: FreshnessStatus;
  date: string | null;
  effective_date: string | null;
  notices: Notice[];
  confirmed_at: string | null;
  confirmation_scope: string | null;
}

export interface ActRef {
  slug: string;
  eli: string;
  short_title: string;
  abbrev: string;
  official_url: string;
}

export interface UnitRef {
  slug: string;
  label: string;
  display_label: string;
  title: string | null;
  url: string;
}

export interface Citation {
  act: string;
  journal: string;
  unit: string;
  as_of: string | null;
  eli: string | null;
  url: string | null;
  text: string;
}

export interface Explanation {
  version_id: number;
  version_no: number;
  state: string;
  title: string | null;
  paragraphs: string[];
  is_demo: boolean;
  /** Szkic napisało AI z tekstu z ELI, sprawdził i opublikował imiennie recenzent. */
  ai_assisted: boolean;
  author: string;
  reviewer: string | null;
  verified_on: string | null;
  published_at: string | null;
  suspended_reason: string | null;
  permalink: string;
}

export interface Amendment {
  eli: string;
  journal: string;
  title: string;
  published_on: string | null;
  entry_into_force: string | null;
  later_than_text: boolean;
  url: string;
}

export interface Validity {
  kind: string;
  valid_from: string | null;
  valid_to: string | null;
  basis: string | null;
  title: string | null;
  source: string;
}

export interface Version {
  unit_version_id: number;
  journal: string;
  text_type: TextType;
  legal_status_date: string | null;
  recorded_at: string;
  is_current: boolean;
  permalink: string;
}

export interface ExplanationVersion {
  id: number;
  version_no: number;
  state: string;
  published_at: string | null;
  verified_on: string | null;
  permalink: string;
}

export interface Related {
  kind: "sciezka" | "kreator" | "pojecie";
  title: string;
  url: string;
}

export interface ProvisionSummary {
  slug: string;
  title: string | null;
  display_label: string;
  act: ActRef;
  text_type: TextType | null;
  freshness: Freshness;
  has_explanation: boolean;
  url: string;
}

export interface Provision {
  slug: string;
  unit_key: string;
  label: string;
  display_label: string;
  title: string | null;
  act: ActRef;
  text_type: TextType | null;
  text_note: string | null;
  paragraphs: Paragraph[];
  freshness: Freshness;
  explanation: Explanation | null;
  explanation_status: "brak" | "opublikowane" | "zawieszone" | "cofniete";
  citation: Citation;
  amendments: Amendment[];
  validity: Validity[];
  versions: Version[];
  explanation_versions: ExplanationVersion[];
  illustration: string | null;
  related: Related[];
  permalink: string;
  is_archived_version: boolean;
  current_url: string;
}

export interface TextVersion {
  id: number;
  text_type: TextType;
  journal: string;
  source_eli: string | null;
  legal_status_date: string | null;
  review_state: string;
  parse_quality: number | null;
  note: string | null;
  origin: string;
  recorded_at: string;
}

export interface Act {
  slug: string;
  eli: string;
  short_title: string;
  abbrev: string;
  title: string;
  act_kind: string;
  area: string;
  in_mvp: boolean;
  official_url: string;
  text_format: string;
  owner: string | null;
  manifest_verified_on: string | null;
  relations: { rola?: string; eli?: string; opis?: string }[];
  current_text: TextVersion | null;
  freshness: Freshness;
  amendments: Amendment[];
  validity: Validity[];
  last_sync_ok: string | null;
  units: UnitRef[];
}

export interface GlossaryTerm {
  slug: string;
  term: string;
  definition: string;
  basis: string | null;
  units: UnitRef[];
  see_also: { slug: string; term: string }[];
  illustration: string | null;
  is_demo: boolean;
  verified_on: string | null;
  state: string;
  version_id: number;
}

/** Definicja ustawowa — dosłowne brzmienie punktu przepisu definicyjnego. */
export interface Definition {
  term: string;
  term_in_text: string;
  paragraphs: Paragraph[];
  unit_slug: string;
  display_label: string;
  act_slug: string;
  act_title: string;
  journal: string;
  freshness: FreshnessStatus;
  url: string;
}

export interface GuideStep {
  title: string;
  who: string | null;
  body: string;
  documents: string[];
  basis: string | null;
  unit: UnitRef | null;
  link: string | null;
  illustration: string | null;
}

export interface GuideSummary {
  slug: string;
  title: string;
  summary: string;
  steps_count: number;
  url: string;
}

export interface Guide {
  slug: string;
  title: string;
  summary: string;
  caveat: string | null;
  steps: GuideStep[];
  units: UnitRef[];
  is_demo: boolean;
  verified_on: string | null;
  state: string;
  version_id: number;
  version_no: number;
}

export interface TreeNode {
  key: string;
  kind: "pytanie" | "wynik";
  step_label: string;
  question: string | null;
  help: string | null;
  options: { label: string; next: string }[];
  result_title: string | null;
  result_body: string | null;
  outcome: string | null;
  basis: string | null;
  units: UnitRef[];
  links: { label: string; url: string }[];
  status: FreshnessStatus | null;
  status_date: string | null;
  status_effective_date: string | null;
  suspended: boolean;
  suspended_reason: string | null;
  /** Wynik „poza zakresem”: przepisy do sprawdzenia według odpowiedzi, która tu prowadzi (dosłownie, bez oceny). */
  to_check: Record<string, ToCheck[]>;
}

export interface ToCheck {
  unit_slug: string;
  label: string;
  intro: string;
  paragraphs: Paragraph[];
  url: string;
  /** Reguła zatwierdzona przez recenzenta dla tego brzmienia. */
  rule: { wymog: string; warunki: string[]; zatwierdzil: string | null } | null;
}

export interface Tree {
  slug: string;
  title: string;
  intro: string | null;
  scope_note: string | null;
  root: string;
  nodes: Record<string, TreeNode>;
  version_id: number;
  version_no: number;
  is_demo: boolean;
  verified_on: string | null;
  state: string;
}

export interface TreeSummary {
  slug: string;
  title: string;
  intro: string | null;
  url: string;
}

export interface SearchHit {
  kind: string;
  kind_label: string;
  ref: string;
  title: string;
  subtitle: string | null;
  snippet: string;
  url: string;
}

export interface SearchResult {
  query: string;
  hits: SearchHit[];
  synonyms_used: { slowo: string; szukamy_tez: string[] }[];
  matched_all_words: boolean;
}

export interface Synonym {
  term: string;
  expansions: string[];
  note: string | null;
}

export interface Run {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  trigger: string;
  stats: Record<string, number>;
  errors: Record<string, string>[];
}

export interface SourceAlarm {
  id: number;
  title: string;
  raised_at: string;
  details: { adres?: string; naruszenia?: { kod: string; opis: string }[] };
}

export interface DataStatus {
  generated_at: string;
  threshold_hours: number;
  last_success_at: string | null;
  /** Otwarty alarm źródła: synchronizacja wstrzymana, wszystkie karty „Nie potwierdzono aktualności”. */
  alarm: SourceAlarm | null;
  runs: Run[];
  acts: {
    slug: string;
    short_title: string;
    last_sync_ok: string | null;
    data_age_hours: number | null;
    freshness: FreshnessStatus;
    text_type: TextType | null;
    journal: string | null;
  }[];
  open_tasks: Record<string, number>;
  recent_fetch_errors: Record<string, string>[];
  demo_content: boolean;
}

export interface Home {
  featured: ProvisionSummary[];
  guides: GuideSummary[];
  trees: TreeSummary[];
  glossary_count: number;
  status: { last_success_at: string | null; demo_content: boolean; threshold_hours: number };
}
