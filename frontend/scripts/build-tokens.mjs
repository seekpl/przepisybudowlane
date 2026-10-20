// Generuje app/tokens.css z design/tokens.json (identyfikacja „Przepisy budowlane”).
// Nie edytuj tokens.css ręcznie — zmieniaj tokens.json i uruchom `npm run tokens`.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const tokens = JSON.parse(readFileSync(resolve(here, "../../design/tokens.json"), "utf8"));
const out = [];
out.push(`/* ${tokens.name} — wygenerowane z design/tokens.json (v${tokens.version}). Nie edytuj ręcznie. */`);

for (const f of tokens.type.fonts) {
  out.push(
    `@font-face { font-family: "${f.family}"; src: url("/${f.file}") format("woff2"); font-weight: ${f.weight}; ` +
      `font-style: ${f.style ?? "normal"}; font-display: swap; }`,
  );
}

const themes = tokens.color.themes.map((t) => t.id);
const colorVars = (theme) =>
  tokens.color.tokens.map((t) => {
    const v = typeof t.value === "string" ? t.value : (t.value[theme] ?? t.value[themes[0]]);
    return `  --${t.name}: ${v};`;
  });

const root = [":root {", "  color-scheme: light;"];
root.push(...colorVars("light"));
for (const [k, v] of Object.entries(tokens.type.families)) root.push(`  --font-${k}: ${v};`);
for (const family of ["spacing", "radius", "layout"]) {
  for (const t of tokens[family]?.tokens ?? []) root.push(`  --${t.name}: ${t.value};`);
}
root.push("}");
out.push(root.join("\n"));

const dark = ["  color-scheme: dark;", ...colorVars("dark")].join("\n");
out.push(`@media (prefers-color-scheme: dark) {\n:root:not([data-theme="light"]) {\n${dark}\n}\n}`);
out.push(`:root[data-theme="dark"] {\n${dark}\n}`);

for (const group of tokens.type.groups) {
  for (const s of group.styles) {
    const rules = [
      `font-family: var(--font-${group.family});`,
      `font-size: ${s.fontSize};`,
      `line-height: ${s.lineHeight};`,
      `font-weight: ${s.fontWeight};`,
    ];
    if (s.letterSpacing) rules.push(`letter-spacing: ${s.letterSpacing};`);
    if (group.family === "mono") rules.push("font-variant-numeric: tabular-nums slashed-zero;");
    out.push(`.${s.name} { ${rules.join(" ")} }`);
  }
}

writeFileSync(resolve(here, "../app/tokens.css"), out.join("\n\n") + "\n");
console.log("app/tokens.css: wygenerowano");
