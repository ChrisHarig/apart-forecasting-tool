import { X } from "lucide-react";
import { SideNav } from "../Navigation/SideNav";
import { useDashboard } from "../../state/DashboardContext";
import { FeedPage } from "../Feed/FeedPage";
import { ExplorerPage } from "../Explorer/ExplorerPage";
import { MapPage } from "../Map/MapPage";
import { NewsPage } from "../News/NewsPage";

export function DashboardShell() {
  const {
    view,
    setView,
    catalog,
    selectedSourceIds,
    toggleSourceSelected,
    clearSelectedSources,
    setScrollTarget
  } = useDashboard();

  const selectedSources = catalog.data?.filter((s) => selectedSourceIds.includes(s.id)) ?? [];

  let content;
  if (view === "explorer") content = <ExplorerPage />;
  else if (view === "map") content = <MapPage />;
  else if (view === "news") content = <NewsPage />;
  else content = <FeedPage />;

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-ink-950 text-white lg:flex-row">
      <aside className="w-full shrink-0 border-b border-white/10 bg-black/95 p-4 backdrop-blur lg:h-screen lg:w-[260px] lg:overflow-y-auto lg:border-b-0 lg:border-r">
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase text-red-300">EPI-Eval</p>
          <h1 className="mt-1 text-xl font-semibold">Pandemic Readiness Workspace</h1>
          <p className="mt-3 text-sm leading-6 text-neutral-400">
            Browse epidemiological data sources from Huggingface and inspect them as graphs, maps, or news feeds.
          </p>
        </div>

        <SideNav active={view} onSelect={setView} />

        <section className="mt-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase text-neutral-400">Selected ({selectedSources.length})</h2>
            {selectedSources.length > 0 && (
              <button
                type="button"
                className="text-xs text-neutral-500 hover:text-red-300"
                onClick={clearSelectedSources}
              >
                Clear
              </button>
            )}
          </div>
          {selectedSources.length === 0 ? (
            <p className="mt-2 text-xs text-neutral-500">
              Add sources from the Feed to keep them here for quick access.
            </p>
          ) : (
            <ul className="mt-2 space-y-1">
              {selectedSources.map((s) => (
                <li key={s.id}>
                  <div className="flex items-center justify-between rounded-md border border-white/10 bg-white/[0.03] px-2 py-1.5 text-xs text-neutral-200 transition hover:border-white/20">
                    <button
                      type="button"
                      onClick={() => {
                        setView("feed");
                        setScrollTarget(s.id);
                      }}
                      className="flex-1 truncate text-left"
                      title={s.pretty_name}
                    >
                      {s.pretty_name}
                    </button>
                    <button
                      type="button"
                      onClick={() => toggleSourceSelected(s.id)}
                      className="ml-1 rounded p-1 text-neutral-500 hover:bg-white/10 hover:text-white"
                      aria-label={`Remove ${s.pretty_name}`}
                    >
                      <X className="h-3 w-3" aria-hidden="true" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>

      <main className="flex-1 overflow-y-auto p-4 lg:p-6 [scrollbar-gutter:stable]">{content}</main>
    </div>
  );
}
