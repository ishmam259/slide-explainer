import { DeckHeader } from "./deck-header";

export default async function DeckLayout({ children, params }: LayoutProps<"/decks/[deckId]">) {
  const { deckId } = await params;
  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <DeckHeader deckId={deckId} />
      <div className="mt-6">{children}</div>
    </div>
  );
}
