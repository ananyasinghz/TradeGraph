interface PlaceholderViewProps {
  title: string;
  description: string;
}

export function PlaceholderView({ title, description }: PlaceholderViewProps) {
  return (
    <section className="placeholder-view">
      <h2>{title}</h2>
      <p>{description}</p>
      <p className="placeholder-meta">
        See <code>docs/IMPLEMENTATION_PLAN.md</code> for Phase 1 delivery of this surface.
      </p>
    </section>
  );
}
