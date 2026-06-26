import { ConfigProvider } from "antd";
import enUS from "antd/locale/en_US";
import zhTW from "antd/locale/zh_TW";
import type { ReactNode } from "react";

import type { Language } from "../../shared/i18n/messages";

type AppProvidersProps = {
  children: ReactNode;
  language: Language;
};

export function AppProviders({ children, language }: AppProvidersProps) {
  return (
    <ConfigProvider
      locale={language === "zh-TW" ? zhTW : enUS}
      theme={{
        token: {
          borderRadius: 8,
          colorPrimary: "#0f766e",
          colorInfo: "#2563eb",
          colorSuccess: "#16a34a",
          colorWarning: "#d97706",
          colorError: "#dc2626",
          fontFamily:
            "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
        },
        components: {
          Layout: {
            bodyBg: "#eef2f6",
            siderBg: "#102033",
            headerBg: "#0b1728"
          },
          Card: {
            borderRadiusLG: 8
          },
          Button: {
            borderRadius: 8
          }
        }
      }}
    >
      {children}
    </ConfigProvider>
  );
}
