import {
  ApiOutlined,
  BarChartOutlined,
  BellOutlined,
  CloudSyncOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  DoubleLeftOutlined,
  DoubleRightOutlined,
  QuestionCircleOutlined,
  SettingOutlined
} from "@ant-design/icons";
import { Badge, Button, Layout, Menu, Tag, Typography } from "antd";
import type { ReactNode } from "react";
import { useState } from "react";

import { DashboardPage } from "../../pages/DashboardPage";
import { DataPage } from "../../pages/DataPage";
import { JobsPage } from "../../pages/JobsPage";
import { SettingsPage } from "../../pages/SettingsPage";
import type { Language } from "../../shared/i18n/messages";
import { messages } from "../../shared/i18n/messages";
import type { AppRouteKey } from "../../shared/types/navigation";

const { Header, Sider, Content } = Layout;

type AppLayoutProps = {
  activeRoute: AppRouteKey;
  language: Language;
  onLanguageChange: (language: Language) => void;
  onRouteChange: (route: AppRouteKey) => void;
};

export function AppLayout({
  activeRoute,
  language,
  onLanguageChange,
  onRouteChange
}: AppLayoutProps) {
  const t = messages[language];
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const expandSidebarLabel = language === "en-US" ? "Expand" : "展開";
  const collapseButtonLabel = sidebarCollapsed ? expandSidebarLabel : t.app.collapse;
  const navItems = [
    { key: "dashboard" as const, icon: <DashboardOutlined />, label: t.nav.dashboard },
    { key: "data" as const, icon: <DatabaseOutlined />, label: t.nav.data },
    { key: "jobs" as const, icon: <CloudSyncOutlined />, label: t.nav.jobs },
    { key: "settings" as const, icon: <SettingOutlined />, label: t.nav.settings }
  ];
  const pageByRoute: Record<AppRouteKey, ReactNode> = {
    dashboard: <DashboardPage messages={t} />,
    data: <DataPage messages={t} />,
    jobs: <JobsPage messages={t} language={language} />,
    settings: <SettingsPage messages={t} language={language} onLanguageChange={onLanguageChange} />
  };

  return (
    <Layout className="app-shell">
      <Header className="app-topbar">
        <div className="topbar-left">
          <div className="brand-block">
            <div className="brand-mark">
              <BarChartOutlined />
            </div>
            <div>
              <Typography.Text className="brand-name">TradeBridge</Typography.Text>
              <Typography.Text className="brand-caption">{t.app.caption}</Typography.Text>
            </div>
          </div>
        </div>
        <div className="topbar-actions">
          <Tag color="geekblue" className="environment-tag">{t.app.local}</Tag>
          <Badge status="success" text={<span className="status-text">{t.app.apiReady}</span>} />
          <Button icon={<QuestionCircleOutlined />} className="topbar-icon-button" aria-label="Help" />
          <Button icon={<BellOutlined />} className="topbar-icon-button" aria-label="Notifications" />
          <Button icon={<ApiOutlined />} className="header-action">
            {t.app.providerStatus}
          </Button>
        </div>
      </Header>

      <Layout className="app-body">
        <Sider
          className={`app-sidebar ${sidebarCollapsed ? "app-sidebar-collapsed" : ""}`}
          width={184}
          collapsedWidth={80}
          collapsed={sidebarCollapsed}
          trigger={null}
        >
          <Menu
            className="side-menu"
            mode="inline"
            inlineCollapsed={sidebarCollapsed}
            selectedKeys={[activeRoute]}
            onClick={({ key }) => onRouteChange(key as AppRouteKey)}
            items={navItems}
          />
          <div className="sidebar-footer">
            <Button
              type="text"
              icon={sidebarCollapsed ? <DoubleRightOutlined /> : <DoubleLeftOutlined />}
              className="collapse-button"
              aria-label={collapseButtonLabel}
              title={collapseButtonLabel}
              onClick={() => setSidebarCollapsed((current) => !current)}
            >
              {sidebarCollapsed ? null : t.app.collapse}
            </Button>
          </div>
        </Sider>
        <Layout className="app-main">
          <nav className="mobile-nav" aria-label="Primary navigation">
            {navItems.map((item) => (
              <button
                className={`mobile-nav-item ${activeRoute === item.key ? "mobile-nav-item-active" : ""}`}
                key={item.key}
                type="button"
                onClick={() => onRouteChange(item.key)}
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
          <Content className="app-content">{pageByRoute[activeRoute]}</Content>
        </Layout>
      </Layout>
    </Layout>
  );
}
