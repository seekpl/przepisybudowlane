import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ProvisionPage } from "@/components/site/ProvisionPage";
import { api } from "@/lib/api";
import { getMode } from "@/lib/mode";

type Props = { params: Promise<{ slug: string; id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug, id } = await params;
  const p = await api.provisionVersion(slug, Number(id));
  return p ? { title: `${p.title ?? p.label} — wersja z ${p.citation.journal}` } : { title: "Nie znaleziono wersji" };
}

export default async function Page({ params }: Props) {
  const { slug, id } = await params;
  const versionId = Number(id);
  if (!Number.isInteger(versionId)) notFound();
  const [p, mode] = await Promise.all([api.provisionVersion(slug, versionId), getMode()]);
  if (!p) notFound();
  return <ProvisionPage p={p} mode={mode} />;
}
