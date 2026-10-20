import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Wizard } from "@/components/ds/Wizard";
import { api } from "@/lib/api";
import { typo } from "@/lib/format";
import { getMode } from "@/lib/mode";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const tree = await api.tree((await params).slug);
  return { title: tree?.title ?? "Kreator" };
}

export default async function Page({ params }: Props) {
  const { slug } = await params;
  const [tree, mode] = await Promise.all([api.tree(slug), getMode()]);
  if (!tree) notFound();
  return (
    <div className="pb-stack-5" style={{ maxWidth: 760 }}>
      <div className="pb-page-head" style={{ marginBottom: 0 }}>
        <p className="ui-label pb-kicker">Kreator</p>
        <h1 className="ui-title">{tree.title}</h1>
        {tree.intro ? <p className="ui-body">{typo(tree.intro)}</p> : null}
        {tree.scope_note ? <p className="ui-small pb-muted">{typo(tree.scope_note)}</p> : null}
      </div>
      <Wizard tree={tree} mode={mode} />
    </div>
  );
}
