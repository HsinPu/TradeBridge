import { Alert, Button, Card, Form, Input, Space, Spin, Typography } from "antd";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ApiError, apiRequest } from "../../shared/api/client";
import type { Language } from "../../shared/i18n/messages";

type Session = { login_required: boolean; authenticated: boolean; username: string | null };
type Props = {
  language: Language;
  onLanguageChange: (language: Language) => void;
  children: (session: Session, logout: () => Promise<void>, busy: boolean) => ReactNode;
};

export function AuthGate({ language, onLanguageChange, children }: Props) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form] = Form.useForm<{ username: string; password: string }>();
  const zh = language === "zh-TW";
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSession(await apiRequest<Session>("/api/v1/auth/session"));
    } catch {
      setError(zh ? "無法連線到服務，請重試。" : "Cannot connect to the service. Please retry.");
    } finally { setLoading(false); }
  }, [zh]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const expired = () => {
      setSession({ login_required: true, authenticated: false, username: null });
      setError(zh ? "登入已失效，請重新登入。" : "Your session expired. Please sign in again.");
    };
    window.addEventListener("tradebridge:auth-required", expired);
    return () => window.removeEventListener("tradebridge:auth-required", expired);
  }, [zh]);

  const login = async (values: { username: string; password: string }) => {
    setBusy(true);
    setError("");
    try {
      setSession(await apiRequest<Session>("/api/v1/auth/login", { method: "POST", body: values }));
      form.resetFields();
    } catch (reason) {
      setError(reason instanceof ApiError && reason.status === 401
        ? (zh ? "帳號或密碼錯誤。" : "Incorrect username or password.")
        : reason instanceof ApiError && reason.status === 429
          ? (zh ? "嘗試次數過多，請一分鐘後再試。" : "Too many attempts. Try again in one minute.")
          : (zh ? "登入失敗，請檢查連線後重試。" : "Sign-in failed. Check your connection and retry."));
      form.setFieldValue("password", "");
    } finally { setBusy(false); }
  };
  const logout = async () => {
    setBusy(true);
    setError("");
    try {
      await apiRequest<void>("/api/v1/auth/logout", { method: "POST" });
      setSession({ login_required: true, authenticated: false, username: null });
    } catch {
      setError(zh ? "登出失敗，請重試。" : "Sign-out failed. Please retry.");
    } finally { setBusy(false); }
  };

  if (loading) return <div className="login-shell"><Spin tip={zh ? "確認登入狀態…" : "Checking session…"}><div className="login-loading" /></Spin></div>;
  if (session?.authenticated) return <>{error && <Alert role="alert" type="error" message={error} />}{children(session, logout, busy)}</>;
  return (
    <main className="login-shell">
      <Card className="login-card">
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          <div>
            <Typography.Title level={2}>TradeBridge</Typography.Title>
            <Typography.Text type="secondary">{zh ? "登入管理介面" : "Sign in to your workspace"}</Typography.Text>
          </div>
          {error && <Alert role="alert" type="error" showIcon message={error} />}
          {!session ? <Button block onClick={() => void load()}>{zh ? "重新連線" : "Retry connection"}</Button> : (
            <Form form={form} layout="vertical" onFinish={login} disabled={busy}>
              <Form.Item name="username" label={zh ? "帳號" : "Username"} rules={[{ required: true, message: zh ? "請輸入帳號" : "Enter your username" }]}>
                <Input autoComplete="username" maxLength={128} autoFocus />
              </Form.Item>
              <Form.Item name="password" label={zh ? "密碼" : "Password"} rules={[{ required: true, message: zh ? "請輸入密碼" : "Enter your password" }]}>
                <Input.Password autoComplete="current-password" maxLength={1024} />
              </Form.Item>
              <Button type="primary" htmlType="submit" block loading={busy}>{zh ? "登入" : "Sign in"}</Button>
            </Form>
          )}
          <div className="login-footer">
            <Typography.Text type="secondary">v{__APP_VERSION__}</Typography.Text>
            <Button type="text" onClick={() => onLanguageChange(zh ? "en-US" : "zh-TW")}>{zh ? "English" : "繁體中文"}</Button>
          </div>
        </Space>
      </Card>
    </main>
  );
}
