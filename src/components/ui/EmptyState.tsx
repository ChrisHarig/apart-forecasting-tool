interface EmptyStateProps {
  title: string;
  body: string;
}

export function EmptyState({ title, body }: EmptyStateProps) {
  return (
    <div className="rounded-md border border-dashed border-white/12 bg-white/[0.025] p-6 text-center">
      <p className="text-sm font-semibold text-slate-200">{title}</p>
      <p className="mt-2 text-sm leading-6 text-slate-400">{body}</p>
    </div>
  );
}
