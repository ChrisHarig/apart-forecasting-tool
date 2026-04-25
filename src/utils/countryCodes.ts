import countries from "i18n-iso-countries";
import en from "i18n-iso-countries/langs/en.json";

countries.registerLocale(en);

export interface CountryReference {
  iso3: string;
  iso2?: string;
  isoNumeric?: string;
  name: string;
}

export function isoNumericToIso3(isoNumeric: string | number | undefined): string | null {
  if (isoNumeric === undefined || isoNumeric === null) return null;
  const normalized = String(isoNumeric).padStart(3, "0");
  return countries.numericToAlpha3(normalized) ?? null;
}

export function iso3ToIsoNumeric(iso3: string | undefined): string | null {
  if (!iso3) return null;
  const iso2 = countries.alpha3ToAlpha2(iso3.toUpperCase());
  if (!iso2) return null;
  return countries.alpha2ToNumeric(iso2) ?? null;
}

export function iso3ToCountryName(iso3: string | undefined): string {
  if (!iso3) return "No country selected";
  return countries.getName(iso3.toUpperCase(), "en") ?? iso3.toUpperCase();
}

export function normalizeIso3(value: string | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  const upper = trimmed.toUpperCase();
  if (countries.isValid(upper) && upper.length === 3) return upper;
  if (countries.isValid(upper) && upper.length === 2) return countries.alpha2ToAlpha3(upper) ?? null;
  return countryNameToIso3(trimmed);
}

export function countryNameToIso3(countryName: string | undefined): string | null {
  if (!countryName) return null;
  const alpha2 = countries.getAlpha2Code(countryName.trim(), "en");
  return alpha2 ? countries.alpha2ToAlpha3(alpha2) ?? null : null;
}

export function getCountryReferenceFromNumeric(isoNumeric: string | number | undefined): CountryReference | null {
  const iso3 = isoNumericToIso3(isoNumeric);
  if (!iso3) return null;
  return {
    iso3,
    iso2: countries.alpha3ToAlpha2(iso3) ?? undefined,
    isoNumeric: iso3ToIsoNumeric(iso3) ?? undefined,
    name: iso3ToCountryName(iso3)
  };
}
