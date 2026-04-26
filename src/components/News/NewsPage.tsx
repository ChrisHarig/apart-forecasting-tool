import { ExternalLink } from "lucide-react";
import { useDashboard } from "../../state/DashboardContext";

export function NewsPage() {
  const { news } = useDashboard();

  return (
    <div className="space-y-4">
      <header className="rounded-2xl border border-white/10 bg-black p-5">
        <p className="text-xs font-semibold uppercase text-red-300">News</p>
        <h1 className="mt-1 text-2xl font-semibold">Public-health newsfeed</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-neutral-400">
          Aggregated outbreak and event reporting for your selected sources.
        </p>
      </header>

      {news.items.length === 0 ? (
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-6 text-sm text-neutral-300">
          <p className="font-semibold text-white">No news feed connected yet.</p>
          <p className="mt-1 text-neutral-400">
            The newsfeed will populate when a feed adapter is connected (e.g. ProMED, WHO DON, HealthMap).
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {news.items.map((item) => (
            <li key={item.id} className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs text-neutral-400">
                {item.source} · {item.publishedAt.slice(0, 10)}
                {item.country && <> · {item.country}</>}
              </p>
              <h3 className="mt-1 text-base font-semibold text-white">{item.headline}</h3>
              {item.summary && <p className="mt-1 text-sm text-neutral-300">{item.summary}</p>}
              {item.url && (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-flex items-center gap-1 text-xs text-red-300 hover:text-red-200"
                >
                  Read source <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
