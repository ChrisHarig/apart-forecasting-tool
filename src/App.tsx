import { WorkspaceShell } from "./components/Layout/WorkspaceShell";
import { DashboardProvider } from "./state/DashboardContext";
import { PredictionsProvider } from "./state/PredictionsContext";
import { WorkspaceProvider } from "./state/WorkspaceContext";

export default function App() {
  return (
    <DashboardProvider>
      <PredictionsProvider>
        <WorkspaceProvider>
          <WorkspaceShell />
        </WorkspaceProvider>
      </PredictionsProvider>
    </DashboardProvider>
  );
}
