export interface NewsItem {
  id: string;
  headline: string;
  source: string;
  url?: string;
  publishedAt: string;
  country?: string;
  relatedSourceIds?: string[];
  summary?: string;
}

export type NewsStatus = "idle" | "loading" | "ready" | "error";

export interface NewsFeed {
  status: NewsStatus;
  items: NewsItem[];
  updatedAt?: string;
  error?: string;
}
