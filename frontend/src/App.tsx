import { useState } from "react";

import { AppLayout } from "./app/layout/AppLayout";
import { AuthGate } from "./app/auth/AuthGate";
import type { Language } from "./shared/i18n/messages";
import type { AppRouteKey } from "./shared/types/navigation";

type AppProps = {
  language: Language;
  onLanguageChange: (language: Language) => void;
};

type WorkspaceProps = AppProps & { username: string | null; onLogout: () => Promise<void>; logoutBusy: boolean };

function Workspace({ language, onLanguageChange, username, onLogout, logoutBusy }: WorkspaceProps) {
  const [activeRoute, setActiveRoute] = useState<AppRouteKey>("dashboard");
  return <AppLayout activeRoute={activeRoute} language={language} onLanguageChange={onLanguageChange}
    onRouteChange={setActiveRoute} username={username} onLogout={onLogout} logoutBusy={logoutBusy} />;
}

export default function App({ language, onLanguageChange }: AppProps) {
  return (
    <AuthGate language={language} onLanguageChange={onLanguageChange}>
      {(session, logout, busy) => <Workspace language={language} onLanguageChange={onLanguageChange}
        username={session.login_required ? session.username : null} onLogout={logout} logoutBusy={busy} />}
    </AuthGate>
  );
}
