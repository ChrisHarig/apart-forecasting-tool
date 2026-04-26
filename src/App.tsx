import { WorkspaceShell } from "./components/Layout/WorkspaceShell";
import { DashboardProvider } from "./state/DashboardContext";
import { WorkspaceProvider } from "./state/WorkspaceContext";

export default function App() {
  return (
    <DashboardProvider>
      <WorkspaceProvider>
        <WorkspaceShell />
      </WorkspaceProvider>
    </DashboardProvider>
  );
}
