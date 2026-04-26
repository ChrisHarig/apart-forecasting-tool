import { Activity, Newspaper, TableProperties } from "lucide-react";
import type { ComponentType, SVGProps } from "react";
import type { DashboardView } from "../../types/dashboard";

interface NavItem {
  id: DashboardView;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
}

const NAV_ITEMS: NavItem[] = [
  { id: "feed", label: "Feed", icon: Activity },
  { id: "explorer", label: "Explorer", icon: TableProperties },
  { id: "news", label: "News", icon: Newspaper }
];

interface Props {
  active: DashboardView;
  onSelect: (view: DashboardView) => void;
}

export function SideNav({ active, onSelect }: Props) {
  return (
    <nav aria-label="Primary dashboard navigation">
      <ul className="flex flex-col gap-1" role="list">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => onSelect(item.id)}
                aria-current={isActive ? "page" : undefined}
                className={`flex w-full items-center gap-3 rounded-md border px-3 py-2 text-left text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600 ${
                  isActive
                    ? "border-red-500/55 bg-red-950/40 text-red-100"
                    : "border-white/10 bg-white/[0.03] text-neutral-300 hover:border-white/20 hover:bg-white/[0.06] hover:text-white"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
