import { useState } from "react";

import { AppLayout } from "./app/layout/AppLayout";
import type { Language } from "./shared/i18n/messages";
import type { AppRouteKey } from "./shared/types/navigation";

type AppProps = {
  language: Language;
  onLanguageChange: (language: Language) => void;
};

export default function App({ language, onLanguageChange }: AppProps) {
  const [activeRoute, setActiveRoute] = useState<AppRouteKey>("dashboard");

  return (
    <AppLayout
      activeRoute={activeRoute}
      language={language}
      onLanguageChange={onLanguageChange}
      onRouteChange={setActiveRoute}
    />
  );
}
