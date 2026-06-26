import React from "react";
import ReactDOM from "react-dom/client";
import { useEffect, useState } from "react";

import App from "./App";
import { AppProviders } from "./app/providers/AppProviders";
import type { Language } from "./shared/i18n/messages";
import "./styles/app.css";

const LANGUAGE_STORAGE_KEY = "tradebridge.language";
const DEFAULT_LANGUAGE: Language = "zh-TW";

function isLanguage(value: string | null): value is Language {
  return value === "zh-TW" || value === "en-US";
}

function getInitialLanguage(): Language {
  const storedLanguage = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);

  return isLanguage(storedLanguage) ? storedLanguage : DEFAULT_LANGUAGE;
}

function Root() {
  const [language, setLanguage] = useState<Language>(getInitialLanguage);

  useEffect(() => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    document.documentElement.lang = language;
  }, [language]);

  return (
    <AppProviders language={language}>
      <App language={language} onLanguageChange={setLanguage} />
    </AppProviders>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
