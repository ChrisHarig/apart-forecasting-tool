/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MAP_STYLE_URL?: string;
  readonly VITE_SENTINEL_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
