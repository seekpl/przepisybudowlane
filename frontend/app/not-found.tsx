import Link from "next/link";

export default function NotFound() {
  return (
    <div className="pb-stack-4" style={{ maxWidth: 640 }}>
      <h1 className="ui-display">Nie ma takiej strony</h1>
      <p className="ui-body">
        Adres mógł się zmienić albo zawierać literówkę. Spróbuj wyszukiwarki albo wróć na <Link href="/">stronę główną</Link>.
      </p>
    </div>
  );
}
