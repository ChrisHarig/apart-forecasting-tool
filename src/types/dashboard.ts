export type DashboardView = "feed" | "explorer" | "map" | "news";

export const DASHBOARD_VIEWS: DashboardView[] = ["feed", "explorer", "map", "news"];

export interface SelectedCountry {
  iso3: string;
  isoNumeric?: string;
  name: string;
}
