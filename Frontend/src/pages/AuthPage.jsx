import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import PageShell from "../components/layout/PageShell";
import { useAuth } from "../context/AuthContext";

const TABS = ["login", "register"];

function validateAuthForm(form) {
  const username = form.username.trim();
  const password = form.password;
  const phone = form.phone.trim();
  const nickname = form.nickname.trim();

  if (username.length < 3) {
    return "用户名至少需要 3 个字符";
  }
  if (username.length > 64) {
    return "用户名不能超过 64 个字符";
  }
  if (password.length < 6) {
    return "密码至少需要 6 个字符";
  }
  if (password.length > 128) {
    return "密码不能超过 128 个字符";
  }
  if (nickname.length > 64) {
    return "昵称不能超过 64 个字符";
  }
  if (phone.length > 32) {
    return "手机号不能超过 32 个字符";
  }
  return "";
}

export default function AuthPage() {
  const navigate = useNavigate();
  const { isAuthenticated, login, register } = useAuth();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({
    username: "",
    password: "",
    nickname: "",
    phone: ""
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  function updateField(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    const validationError = validateAuthForm(form);
    if (validationError) {
      setError(validationError);
      return;
    }
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login({
          username: form.username.trim(),
          password: form.password
        });
      } else {
        await register({
          username: form.username.trim(),
          password: form.password,
          nickname: form.nickname.trim() || null,
          phone: form.phone.trim() || null
        });
      }
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PageShell compact>
      <section className="auth-layout">
        <div className="auth-brand-panel">
          <span className="eyebrow">Compute Rental Access</span>
          <h1>登录后进入你的专属算力空间</h1>
          <p>
            延续封面页的浅色科技感与轻量玻璃质感。登录后我们会把你带回封面页，再由右上角
            <strong> 立即租赁 </strong>
            进入租赁流程。
          </p>
          <div className="auth-brand-points">
            <div>
              <strong>统一个人区</strong>
              <span>封面页、卡型页和结果页右上角都展示个人入口。</span>
            </div>
            <div>
              <strong>租单归属到人</strong>
              <span>所有租赁记录、历史订单和余额都与当前用户绑定。</span>
            </div>
            <div>
              <strong>个人中心独立管理</strong>
              <span>进行中与历史订单分开展示，查看更直接。</span>
            </div>
          </div>
          <Link className="secondary-link auth-back-link" to="/">
            返回封面页
          </Link>
        </div>

        <div className="auth-card">
          <div className="auth-tab-wrap">
            {TABS.map((tab) => (
              <button
                key={tab}
                className={`auth-tab ${mode === tab ? "auth-tab-active" : ""}`}
                onClick={() => {
                  setMode(tab);
                  setError("");
                }}
                type="button"
              >
                {tab === "login" ? "登录" : "注册"}
              </button>
            ))}
          </div>

          <div className="auth-card-head">
            <h2>{mode === "login" ? "欢迎回来" : "创建账号"}</h2>
            <p>
              {mode === "login"
                ? "登录后即可管理正在租赁的算力实例与账单记录。"
                : "注册成功后会自动登录，并先回到封面页。"}
            </p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <label className="field">
              <span>用户名</span>
              <input
                value={form.username}
                onChange={(event) => updateField("username", event.target.value)}
                placeholder="请输入用户名"
              />
            </label>

            {mode === "register" ? (
              <>
                <label className="field">
                  <span>昵称</span>
                  <input
                    value={form.nickname}
                    onChange={(event) => updateField("nickname", event.target.value)}
                    placeholder="请输入昵称"
                  />
                </label>

                <label className="field">
                  <span>手机号</span>
                  <input
                    value={form.phone}
                    onChange={(event) => updateField("phone", event.target.value)}
                    placeholder="请输入手机号"
                  />
                </label>
              </>
            ) : null}

            <label className="field">
              <span>密码</span>
              <input
                type="password"
                value={form.password}
                onChange={(event) => updateField("password", event.target.value)}
                placeholder="请输入密码"
              />
            </label>

            {error ? <div className="error-banner auth-error">{error}</div> : null}

            <button className="primary-action auth-submit" disabled={submitting} type="submit">
              {submitting ? "提交中..." : mode === "login" ? "登录" : "注册"}
            </button>
          </form>

          {mode === "login" ? (
            <p className="auth-default-tip">默认账户：gpu_user_001 / 123456</p>
          ) : null}
        </div>
      </section>
    </PageShell>
  );
}
