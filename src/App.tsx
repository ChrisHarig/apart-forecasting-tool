import { DashboardShell } from "./components/Layout/DashboardShell";
import { DashboardProvider } from "./state/DashboardContext";

export default function App() {
  return (
    <DashboardProvider>
      <DashboardShell />
    </DashboardProvider>
  );
}
