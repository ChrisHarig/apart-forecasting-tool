export type DashboardView = "feed" | "explorer" | "news";

export const DASHBOARD_VIEWS: DashboardView[] = ["feed", "explorer", "news"];

export interface SelectedCountry {
  iso3: string;
  isoNumeric?: string;
  name: string;
}
