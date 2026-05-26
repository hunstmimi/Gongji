import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AdminShell from "../components/admin/AdminShell";
import { getAdminMachines, getAdminUsage } from "../services/api";

function formatNumber(value, digits = 2) {
  const number = Number(value ?? 0);
  return number.toFixed(digits).replace(/\.00$/, "");
}

function agentText(status) {
  if (status === "online") {
    return "在线";
  }
  if (status === "stale") {
    return "心跳过期";
  }
  return "等待心跳";
}

export default function AdminPage() {
  const [overview, setOverview] = useState(null);
  const [machineData, setMachineData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([getAdminUsage(), getAdminMachines()])
      .then(([usage, machines]) => {
        if (!active) {
          return;
        }
        setOverview(usage);
        setMachineData(machines);
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

  const machines = machineData?.machines ?? [];
  const waitingMachines = useMemo(
    () => machines.filter((item) => item.agent_status !== "online"),
    [machines]
  );
  const activeUsers = overview?.users?.filter((item) => Number(item.current_card_count ?? 0) > 0) ?? [];
  const topRanking = overview?.ranking?.slice(0, 3) ?? [];

  return (
    <AdminShell
      title="后台控制台"
      description="把机器接入、用户占卡和资源状态拆成独立工作区，先看总览，再进入具体操作。"
    >
      {error ? <div className="error-banner">{error}</div> : null}
      {loading ? <div className="empty-state">正在加载后台数据...</div> : null}

      {!loading && overview && machineData ? (
        <div className="admin-layout">
          <div className="admin-summary-grid">
            <div className="admin-metric">
              <span>可租卡数</span>
              <strong>{machineData.summary.available_cards}</strong>
              <em>{machineData.summary.online_agents} 台 Agent 在线</em>
            </div>
            <div className="admin-metric">
              <span>接入机器</span>
              <strong>{machineData.summary.total_machines}</strong>
              <em>{waitingMachines.length} 台需关注</em>
            </div>
            <div className="admin-metric">
              <span>当前占用卡数</span>
              <strong>{overview.summary.total_current_cards}</strong>
              <em>{overview.summary.active_users} 个活跃用户</em>
            </div>
            <div className="admin-metric">
              <span>当月卡时</span>
              <strong>{formatNumber(overview.summary.total_month_card_hours)}</strong>
              <em>{overview.month}</em>
            </div>
          </div>

          <div className="admin-overview-grid">
            <Link className="admin-action-card admin-action-primary" to="/admin/machines">
              <span>机器运维</span>
              <strong>添加机器 / 检测环境 / 部署 Agent</strong>
              <p>处理新机器上线、Agent 心跳、设备状态和可租卡位。</p>
            </Link>
            <Link className="admin-action-card" to="/admin/usage">
              <span>用户用量</span>
              <strong>查看占卡用户和当月排行</strong>
              <p>统计当前谁在占卡、每个用户的活跃租单和当月卡时。</p>
            </Link>
          </div>

          <div className="admin-content-grid">
            <section className="admin-panel">
              <div className="admin-panel-head">
                <div>
                  <h2>需要关注的机器</h2>
                  <p>等待心跳或心跳过期的机器不会稳定进入租赁流程。</p>
                </div>
                <strong>{waitingMachines.length} 台</strong>
              </div>
              <div className="admin-machine-list admin-machine-list-compact">
                {waitingMachines.map((machine) => (
                  <article key={machine.cabinet_code} className="admin-machine-row">
                    <div className="machine-main">
                      <strong>{machine.cabinet_code}</strong>
                      <span>{machine.location} · {machine.host_ip}:{machine.ssh_port}</span>
                    </div>
                    <div className="machine-tags">
                      <span>{machine.card_type}</span>
                      <span className={`agent-pill agent-pill-${machine.agent_status}`}>
                        {agentText(machine.agent_status)}
                      </span>
                    </div>
                  </article>
                ))}
                {waitingMachines.length === 0 ? <div className="admin-empty">当前接入机器心跳正常。</div> : null}
              </div>
            </section>

            <section className="admin-panel">
              <div className="admin-panel-head">
                <div>
                  <h2>当月占卡前三</h2>
                  <p>按本月累计卡时排序。</p>
                </div>
              </div>
              <div className="ranking-list">
                {topRanking.map((item, index) => (
                  <article key={item.user_id} className={`ranking-card ranking-card-${index + 1}`}>
                    <span className="ranking-index">#{index + 1}</span>
                    <div>
                      <h3>{item.nickname || item.username}</h3>
                      <p>{item.username}</p>
                    </div>
                    <strong>{formatNumber(item.month_card_hours)} 卡时</strong>
                  </article>
                ))}
                {topRanking.length === 0 ? <div className="admin-empty">本月还没有租赁记录。</div> : null}
              </div>
            </section>
          </div>

          <section className="admin-panel">
            <div className="admin-panel-head">
              <div>
                <h2>当前占卡用户</h2>
                <p>这里只展示活跃占卡用户，完整明细进入用户统计页。</p>
              </div>
              <Link className="secondary-link" to="/admin/usage">
                查看全部
              </Link>
            </div>
            <div className="active-user-list">
              {activeUsers.map((item) => (
                <div key={item.user_id} className="active-user-row">
                  <div>
                    <strong>{item.nickname || item.username}</strong>
                    <span>{item.active_rentals?.map((rental) => `${rental.card_type} ${rental.card_count}卡`).join("，")}</span>
                  </div>
                  <em>{item.current_card_count} 卡</em>
                </div>
              ))}
              {activeUsers.length === 0 ? <div className="admin-empty">当前没有用户占卡。</div> : null}
            </div>
          </section>
        </div>
      ) : null}
    </AdminShell>
  );
}
