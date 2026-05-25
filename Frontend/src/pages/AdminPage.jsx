import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import HeaderUserSection from "../components/layout/HeaderUserSection";
import PageShell from "../components/layout/PageShell";
import { getAdminUsage } from "../services/api";

function formatNumber(value, digits = 2) {
  const number = Number(value ?? 0);
  return number.toFixed(digits).replace(/\.00$/, "");
}

function activeRentalText(user) {
  const rentals = user.active_rentals ?? [];
  if (!rentals.length) {
    return "当前无活跃租单";
  }
  return rentals
    .map((item) => `${item.card_type} ${item.card_count}卡`)
    .join("，");
}

export default function AdminPage() {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getAdminUsage()
      .then((data) => {
        if (active) {
          setOverview(data);
        }
      })
      .catch((err) => {
        if (active) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const users = overview?.users ?? [];
  const activeUsers = useMemo(
    () => users.filter((item) => Number(item.current_card_count ?? 0) > 0),
    [users]
  );

  return (
    <PageShell compact>
      <header className="standard-header admin-header">
        <div>
          <span className="eyebrow">Admin Console</span>
          <h1>用户占卡统计</h1>
          <p>统计每个用户的当前占卡、活跃租单、当月累计卡时，并生成当月占卡前三排行榜。</p>
        </div>
        <div className="header-action-group">
          <Link className="secondary-link" to="/">
            返回算力网络
          </Link>
          <HeaderUserSection />
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}
      {loading ? <div className="empty-state">正在加载后台统计...</div> : null}

      {!loading && overview ? (
        <section className="admin-layout">
          <div className="admin-summary-grid">
            <div className="admin-metric">
              <span>当前占用卡数</span>
              <strong>{overview.summary.total_current_cards}</strong>
              <em>全部用户合计</em>
            </div>
            <div className="admin-metric">
              <span>活跃用户</span>
              <strong>{overview.summary.active_users}</strong>
              <em>正在占卡的用户</em>
            </div>
            <div className="admin-metric">
              <span>当月卡时</span>
              <strong>{formatNumber(overview.summary.total_month_card_hours)}</strong>
              <em>{overview.month}</em>
            </div>
            <div className="admin-metric">
              <span>用户总数</span>
              <strong>{overview.summary.total_users}</strong>
              <em>已注册账号</em>
            </div>
          </div>

          <div className="admin-content-grid">
            <section className="admin-panel admin-ranking-panel">
              <div className="admin-panel-head">
                <div>
                  <h2>当月占卡前三</h2>
                  <p>按卡时排序：租用卡数乘以本月占用小时数。</p>
                </div>
              </div>

              <div className="ranking-list">
                {(overview.ranking ?? []).map((item, index) => (
                  <article key={item.user_id} className={`ranking-card ranking-card-${index + 1}`}>
                    <span className="ranking-index">#{index + 1}</span>
                    <div>
                      <h3>{item.nickname || item.username}</h3>
                      <p>{item.username}</p>
                    </div>
                    <strong>{formatNumber(item.month_card_hours)} 卡时</strong>
                  </article>
                ))}
                {(overview.ranking ?? []).length === 0 ? (
                  <div className="admin-empty">本月还没有租赁记录。</div>
                ) : null}
              </div>
            </section>

            <section className="admin-panel">
              <div className="admin-panel-head">
                <div>
                  <h2>当前占卡用户</h2>
                  <p>用于快速确认现在谁占用了哪些卡。</p>
                </div>
                <strong>{activeUsers.length} 人</strong>
              </div>

              <div className="active-user-list">
                {activeUsers.map((item) => (
                  <div key={item.user_id} className="active-user-row">
                    <div>
                      <strong>{item.nickname || item.username}</strong>
                      <span>{activeRentalText(item)}</span>
                    </div>
                    <em>{item.current_card_count} 卡</em>
                  </div>
                ))}
                {activeUsers.length === 0 ? <div className="admin-empty">当前没有用户占卡。</div> : null}
              </div>
            </section>
          </div>

          <section className="admin-panel admin-table-panel">
            <div className="admin-panel-head">
              <div>
                <h2>用户使用明细</h2>
                <p>包括当前占卡、活跃租单、当月租单数和当月累计卡时。</p>
              </div>
              <span>生成时间 {overview.generated_at}</span>
            </div>

            <div className="admin-table-wrap">
              <table className="admin-usage-table">
                <thead>
                  <tr>
                    <th>用户</th>
                    <th>当前占卡</th>
                    <th>活跃租单</th>
                    <th>当月租单数</th>
                    <th>当月卡时</th>
                    <th>当前资源</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((item) => (
                    <tr key={item.user_id}>
                      <td>
                        <strong>{item.nickname || item.username}</strong>
                        <span>{item.username}</span>
                      </td>
                      <td>{item.current_card_count}</td>
                      <td>{item.current_rental_count}</td>
                      <td>{item.month_rental_count}</td>
                      <td>{formatNumber(item.month_card_hours)}</td>
                      <td>{activeRentalText(item)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </section>
      ) : null}
    </PageShell>
  );
}
