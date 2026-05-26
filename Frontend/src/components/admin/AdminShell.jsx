import { NavLink, Link } from "react-router-dom";
import HeaderUserSection from "../layout/HeaderUserSection";
import PageShell from "../layout/PageShell";

const NAV_ITEMS = [
  { to: "/admin", label: "控制台", description: "资源和运行概览", end: true },
  { to: "/admin/machines", label: "机器管理", description: "接入、检测、部署 Agent" },
  { to: "/admin/usage", label: "用户统计", description: "占卡排行和明细" }
];

export default function AdminShell({ eyebrow = "Admin Console", title, description, children, actions = null }) {
  return (
    <PageShell compact>
      <header className="standard-header admin-header">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <div className="header-action-group">
          {actions}
          <Link className="secondary-link" to="/">
            返回算力网络
          </Link>
          <HeaderUserSection />
        </div>
      </header>

      <section className="admin-console-shell">
        <aside className="admin-sidebar">
          <div className="admin-sidebar-title">
            <strong>后台控制台</strong>
            <span>分区处理运维任务</span>
          </div>
          <nav className="admin-nav-list">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => `admin-nav-link ${isActive ? "admin-nav-link-active" : ""}`}
              >
                <strong>{item.label}</strong>
                <span>{item.description}</span>
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="admin-workspace">{children}</main>
      </section>
    </PageShell>
  );
}
