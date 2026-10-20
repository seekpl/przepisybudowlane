import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ProvisionPage } from "@/components/site/ProvisionPage";
import { api } from "@/lib/api";
import { getMode } from "@/lib/mode";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<{ objasnienie?: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const p = await api.provision((await params).slug);
  return p ? { title: `${p.title ?? p.label} (${p.display_label})` } : { title: "Nie znaleziono przepisu" };
}

export default async function Page({ params, searchParams }: Props) {
  const { slug } = await params;
  const explanation = Number((await searchParams).objasnienie) || undefined;
  const [p, mode] = await Promise.all([api.provision(slug, explanation), getMode()]);
  if (!p) notFound();
  return <ProvisionPage p={p} mode={mode} />;
}
