import type { ReactNode } from "react";

interface StatusPillProps {
  tone?: "red" | "redSoft" | "light" | "neutral";
  children: ReactNode;
}

const toneClass: Record<NonNullable<StatusPillProps["tone"]>, string> = {
  red: "border-red-500/40 bg-red-950/35 text-red-200",
  redSoft: "border-red-300/35 bg-red-500/10 text-red-100",
  light: "border-neutral-200/25 bg-white/[0.07] text-neutral-100",
  neutral: "border-neutral-400/25 bg-neutral-400/10 text-neutral-300"
};

export function StatusPill({ tone = "neutral", children }: StatusPillProps) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[0.7rem] font-semibold uppercase ${toneClass[tone]}`}>
      {children}
    </span>
  );
}
