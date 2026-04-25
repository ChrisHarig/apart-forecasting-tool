import type { ComponentType, SVGProps } from "react";
import { Database, Globe2, LineChart } from "lucide-react";

export type SideNavItemId = "world-dashboard" | "sources" | "time-series";

export interface SideNavProps {
  activeItem: SideNavItemId;
  onSelect: (item: SideNavItemId) => void;
  className?: string;
  ariaLabel?: string;
  disabledItems?: SideNavItemId[];
}

interface SideNavItem {
  id: SideNavItemId;
  label: "World Dashboard" | "Sources" | "Time Series";
  icon: ComponentType<SVGProps<SVGSVGElement>>;
}

const sideNavItems: readonly SideNavItem[] = [
  { id: "world-dashboard", label: "World Dashboard", icon: Globe2 },
  { id: "sources", label: "Sources", icon: Database },
  { id: "time-series", label: "Time Series", icon: LineChart }
];

export const SIDE_NAV_ITEMS = sideNavItems.map(({ id, label }) => ({ id, label }));

export function SideNav({
  activeItem,
  onSelect,
  className = "",
  ariaLabel = "Primary dashboard navigation",
  disabledItems = []
}: SideNavProps) {
  return (
    <nav className={className} aria-label={ariaLabel}>
      <ul className="flex gap-2 lg:flex-col" role="list">
        {sideNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeItem === item.id;
          const isDisabled = disabledItems.includes(item.id);

          return (
            <li key={item.id}>
              <button
                className={`flex w-full items-center gap-3 rounded-md border px-3 py-2 text-left text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600 disabled:cursor-not-allowed disabled:opacity-50 ${
                  isActive
                    ? "border-red-500/55 bg-red-950/45 text-red-100"
                    : "border-white/10 bg-white/[0.03] text-neutral-300 hover:border-white/15 hover:bg-white/[0.06] hover:text-white"
                }`}
                type="button"
                aria-current={isActive ? "page" : undefined}
                disabled={isDisabled}
                onClick={() => onSelect(item.id)}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="truncate">{item.label}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
