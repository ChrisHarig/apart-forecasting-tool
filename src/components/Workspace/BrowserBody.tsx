import { useWorkspace, type BrowserPane } from "../../state/WorkspaceContext";
import { FeedPage } from "../Feed/FeedPage";

export function BrowserBody({ pane }: { pane: BrowserPane }) {
  const { openExplorerInPane } = useWorkspace();
  return <FeedPage onOpen={(sourceId) => openExplorerInPane(pane.id, sourceId)} />;
}
