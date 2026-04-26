import { useWorkspace } from "../../state/WorkspaceContext";
import { PaneFrame } from "./PaneFrame";

export function WorkspaceGrid() {
  const { panes } = useWorkspace();
  const n = panes.length;
  return (
    <div className={`h-full w-full gap-2 p-2 ${gridClasses(n)}`}>
      {panes.map((p, i) => (
        <div key={p.id} className={`min-h-0 ${paneSpan(n, i)}`}>
          <PaneFrame pane={p} />
        </div>
      ))}
    </div>
  );
}

// 1 pane: full
// 2 panes: 1×2 (side by side)
// 3 panes: 2 on top, 1 spanning the bottom
// 4 panes: 2×2
function gridClasses(n: number): string {
  switch (n) {
    case 1:
      return "grid grid-cols-1 grid-rows-1";
    case 2:
      return "grid grid-cols-2 grid-rows-1";
    case 3:
    case 4:
      return "grid grid-cols-2 grid-rows-2";
    default:
      return "grid grid-cols-1 grid-rows-1";
  }
}

function paneSpan(n: number, i: number): string {
  // Third pane in a 3-pane layout takes the entire bottom row.
  if (n === 3 && i === 2) return "col-span-2";
  return "";
}
