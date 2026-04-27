import { useWorkspace, type BrowserPane } from "../../state/WorkspaceContext";
import { FeedPage } from "../Feed/FeedPage";

export function BrowserBody({ pane }: { pane: BrowserPane }) {
  const { openExplorerInPane, openUserDatasetInPane } = useWorkspace();
  return (
    <FeedPage
      onOpen={(sourceId) => openExplorerInPane(pane.id, sourceId)}
      onOpenUserDataset={(id) => openUserDatasetInPane(pane.id, id)}
    />
  );
}
