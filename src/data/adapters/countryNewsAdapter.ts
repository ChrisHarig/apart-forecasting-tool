import type { CountryNewsSummary } from "../../types/news";

export const countryNewsAdapter = {
  async getLatestForCountry(countryIso3: string): Promise<CountryNewsSummary> {
    // Future endpoint shape: GET /api/countries/:iso3/news/latest
    // Frontend MVP intentionally does not scrape websites or fabricate news.
    return {
      countryIso3,
      status: "ready",
      items: [],
      updatedAt: new Date().toISOString()
    };
  }
};
