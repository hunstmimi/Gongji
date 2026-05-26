import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import HeaderUserSection from "../components/layout/HeaderUserSection";
import PageShell from "../components/layout/PageShell";
import {
  createAdminMachine,
  deployAdminMachineAgent,
  getAdminMachines,
  getAdminUsage,
  probeAdminMachine
} from "../services/api";

const DEFAULT_FORM = {
  cabinet_code: "",
  location: "位置2",
  host_ip: "",
  ssh_port: 22,
  card_type: "3090",
  cabinet_type: "单卡机柜",
  capacity_cards: 1,
  day_hourly_power_cost: 1.8,
  night_hourly_power_cost: 1.6,
  ssh_username: "",
  ssh_password: "",
  sudo_password: ""
};

const POWER_DEFAULTS = {
  "3090-单卡机柜": { capacity_cards: 1, day_hourly_power_cost: 1.8, night_hourly_power_cost: 1.6 },
  "4090-单卡机柜": { capacity_cards: 1, day_hourly_power_cost: 2.4, night_hourly_power_cost: 2.0 },
  "910B3-8卡机柜": { capacity_cards: 8, day_hourly_power_cost: 16.0, night_hourly_power_cost: 12.8 }
};

function formatNumber(value, digits = 2) {
  const number = Number(value ?? 0);
  return number.toFixed(digits).replace(/\.00$/, "");
}

function activeRentalText(user) {
  const rentals = user.active_rentals ?? [];
  if (!rentals.length) {
    return "当前无活跃租单";
  }
  return rentals.map((item) => `${item.card_type} ${item.card_count}卡`).join("，");
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

function observedText(status) {
  const labels = {
    idle: "空闲",
    occupied_unknown: "外部占用",
    platform_rented: "租赁中",
    unhealthy: "异常",
    disabled: "禁用",
    unknown: "未上报"
  };
  return labels[status] ?? status ?? "未上报";
}

export default function AdminPage() {
  const [overview, setOverview] = useState(null);
  const [machineData, setMachineData] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [probing, setProbing] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [probeResult, setProbeResult] = useState(null);
  const [deployResult, setDeployResult] = useState(null);
  const [error, setError] = useState("");
  const [machineMessage, setMachineMessage] = useState("");

  const loadData = () => {
    setError("");
    setLoading(true);
    Promise.all([getAdminUsage(), getAdminMachines()])
      .then(([usage, machines]) => {
        setOverview(usage);
        setMachineData(machines);
      })
      .catch((err) => {
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    loadData();
  }, []);

  const users = overview?.users ?? [];
  const activeUsers = useMemo(
    () => users.filter((item) => Number(item.current_card_count ?? 0) > 0),
    [users]
  );
  const machines = machineData?.machines ?? [];
  const locations = machineData?.locations?.length ? machineData.locations : ["位置1", "位置2", "位置3", "位置4"];
  const cardOptions = machineData?.card_options?.length
    ? machineData.card_options
    : [
        { card_type: "3090", cabinet_type: "单卡机柜", title: "3090", default_capacity_cards: 1 },
        { card_type: "4090", cabinet_type: "单卡机柜", title: "4090", default_capacity_cards: 1 },
        { card_type: "910B3", cabinet_type: "8卡机柜", title: "910B3", default_capacity_cards: 8 }
      ];

  const updateField = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
    setProbeResult(null);
    setDeployResult(null);
  };

  const selectMachineType = (value) => {
    const [card_type, cabinet_type] = value.split("|");
    const defaults = POWER_DEFAULTS[`${card_type}-${cabinet_type}`] ?? {
      capacity_cards: cabinet_type.includes("8") ? 8 : 1,
      day_hourly_power_cost: form.day_hourly_power_cost,
      night_hourly_power_cost: form.night_hourly_power_cost
    };
    setForm((current) => ({
      ...current,
      card_type,
      cabinet_type,
      ...defaults
    }));
  };

  const submitMachine = (event) => {
    event.preventDefault();
    setCreating(true);
    setError("");
    setMachineMessage("");
    createAdminMachine({
      cabinet_code: form.cabinet_code,
      location: form.location,
      host_ip: form.host_ip,
      ssh_port: Number(form.ssh_port),
      card_type: form.card_type,
      cabinet_type: form.cabinet_type,
      capacity_cards: Number(form.capacity_cards),
      day_hourly_power_cost: Number(form.day_hourly_power_cost),
      night_hourly_power_cost: Number(form.night_hourly_power_cost)
    })
      .then((data) => {
        setMachineMessage(data.message ?? "机器已添加");
        setForm(DEFAULT_FORM);
        setProbeResult(null);
        setDeployResult(null);
        return getAdminMachines();
      })
      .then((data) => {
        setMachineData(data);
      })
      .catch((err) => {
        setError(err.message);
      })
      .finally(() => {
        setCreating(false);
      });
  };

  const accessPayload = () => ({
    ...form,
    ssh_port: Number(form.ssh_port),
    capacity_cards: Number(form.capacity_cards),
    day_hourly_power_cost: Number(form.day_hourly_power_cost),
    night_hourly_power_cost: Number(form.night_hourly_power_cost)
  });

  const probeMachine = () => {
    setProbing(true);
    setError("");
    setMachineMessage("");
    setDeployResult(null);
    probeAdminMachine(accessPayload())
      .then((data) => {
        setProbeResult(data);
        setMachineMessage(data.can_deploy ? "检测通过，可以部署 Agent" : "检测未通过，请按提示处理后重试");
      })
      .catch((err) => {
        setError(err.message);
      })
      .finally(() => {
        setProbing(false);
      });
  };

  const deployAgent = () => {
    setDeploying(true);
    setError("");
    setMachineMessage("");
    deployAdminMachineAgent(accessPayload())
      .then((data) => {
        setDeployResult(data);
        setProbeResult({ can_deploy: data.can_deploy, checks: data.checks ?? [] });
        setMachineMessage(data.message ?? "部署流程已结束");
        return getAdminMachines();
      })
      .then((data) => {
        setMachineData(data);
      })
      .catch((err) => {
        setError(err.message);
      })
      .finally(() => {
        setDeploying(false);
      });
  };

  const canDeploy = Boolean(probeResult?.can_deploy) && !deploying;

  return (
    <PageShell compact>
      <header className="standard-header admin-header">
        <div>
          <span className="eyebrow">Admin Console</span>
          <h1>后台管理</h1>
          <p>管理用户占卡统计、机器接入状态和可租资源分布。</p>
        </div>
        <div className="header-action-group">
          <Link className="secondary-link" to="/">
            返回算力网络
          </Link>
          <HeaderUserSection />
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}
      {machineMessage ? <div className="success-banner">{machineMessage}</div> : null}
      {loading ? <div className="empty-state">正在加载后台数据...</div> : null}

      {!loading && overview && machineData ? (
        <section className="admin-layout">
          <div className="admin-summary-grid">
            <div className="admin-metric">
              <span>当前占用卡数</span>
              <strong>{overview.summary.total_current_cards}</strong>
              <em>全部用户合计</em>
            </div>
            <div className="admin-metric">
              <span>可租卡数</span>
              <strong>{machineData.summary.available_cards}</strong>
              <em>{machineData.summary.online_agents} 台 Agent 在线</em>
            </div>
            <div className="admin-metric">
              <span>接入机器</span>
              <strong>{machineData.summary.total_machines}</strong>
              <em>含等待心跳机器</em>
            </div>
            <div className="admin-metric">
              <span>当月卡时</span>
              <strong>{formatNumber(overview.summary.total_month_card_hours)}</strong>
              <em>{overview.month}</em>
            </div>
          </div>

          <div className="admin-content-grid admin-machine-grid">
            <section className="admin-panel">
              <div className="admin-panel-head">
                <div>
                  <h2>添加新机器</h2>
                  <p>新增后先等待 Agent 心跳确认，确认空闲后才会进入用户可租列表。</p>
                </div>
              </div>

              <form className="admin-machine-form" onSubmit={submitMachine}>
                <label>
                  <span>机器编号</span>
                  <input
                    value={form.cabinet_code}
                    onChange={(event) => updateField("cabinet_code", event.target.value)}
                    placeholder="例如 10.20.12.230-4090"
                    required
                  />
                </label>
                <label>
                  <span>机器 IP</span>
                  <input
                    value={form.host_ip}
                    onChange={(event) => updateField("host_ip", event.target.value)}
                    placeholder="10.20.12.230"
                    required
                  />
                </label>
                <label>
                  <span>位置</span>
                  <input
                    list="admin-locations"
                    value={form.location}
                    onChange={(event) => updateField("location", event.target.value)}
                    required
                  />
                  <datalist id="admin-locations">
                    {locations.map((item) => (
                      <option key={item} value={item} />
                    ))}
                  </datalist>
                </label>
                <label>
                  <span>SSH 端口</span>
                  <input
                    type="number"
                    min="1"
                    max="65535"
                    value={form.ssh_port}
                    onChange={(event) => updateField("ssh_port", event.target.value)}
                    required
                  />
                </label>
                <label>
                  <span>卡型/机型</span>
                  <select value={`${form.card_type}|${form.cabinet_type}`} onChange={(event) => selectMachineType(event.target.value)}>
                    {cardOptions.map((item) => (
                      <option key={`${item.card_type}|${item.cabinet_type}`} value={`${item.card_type}|${item.cabinet_type}`}>
                        {item.title || item.card_type} / {item.cabinet_type}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>卡数</span>
                  <input
                    type="number"
                    min="1"
                    max="16"
                    value={form.capacity_cards}
                    onChange={(event) => updateField("capacity_cards", event.target.value)}
                    required
                  />
                </label>
                <label>
                  <span>白天电费成本/小时</span>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    value={form.day_hourly_power_cost}
                    onChange={(event) => updateField("day_hourly_power_cost", event.target.value)}
                    required
                  />
                </label>
                <label>
                  <span>夜间电费成本/小时</span>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    value={form.night_hourly_power_cost}
                    onChange={(event) => updateField("night_hourly_power_cost", event.target.value)}
                    required
                  />
                </label>
                <label>
                  <span>SSH 用户名</span>
                  <input
                    value={form.ssh_username}
                    onChange={(event) => updateField("ssh_username", event.target.value)}
                    placeholder="testsv"
                    autoComplete="username"
                  />
                </label>
                <label>
                  <span>SSH 密码</span>
                  <input
                    type="password"
                    value={form.ssh_password}
                    onChange={(event) => updateField("ssh_password", event.target.value)}
                    placeholder="仅本次检测/部署使用"
                    autoComplete="current-password"
                  />
                </label>
                <label className="admin-machine-wide">
                  <span>sudo 密码</span>
                  <input
                    type="password"
                    value={form.sudo_password}
                    onChange={(event) => updateField("sudo_password", event.target.value)}
                    placeholder="不填则默认同 SSH 密码"
                    autoComplete="current-password"
                  />
                </label>

                <div className="admin-machine-actions">
                  <button className="secondary-button admin-machine-secondary" type="button" onClick={probeMachine} disabled={probing || !form.ssh_username || !form.ssh_password}>
                    {probing ? "正在检测..." : "检测环境"}
                  </button>
                  <button className="primary-button admin-machine-submit" type="button" onClick={deployAgent} disabled={!canDeploy}>
                    {deploying ? "正在部署..." : "一键部署并添加"}
                  </button>
                  <button className="ghost-button admin-machine-ghost" type="submit" disabled={creating}>
                    {creating ? "正在录入..." : "只录入机器"}
                  </button>
                </div>
              </form>

              {probeResult?.checks?.length ? (
                <div className="probe-result-panel">
                  <div className="probe-result-head">
                    <strong>{probeResult.can_deploy ? "检测通过" : "检测未通过"}</strong>
                    <span>{probeResult.can_deploy ? "可以执行 Agent 部署" : "按失败项处理后重试"}</span>
                  </div>
                  <div className="probe-check-list">
                    {probeResult.checks.map((item) => (
                      <div key={item.key} className={`probe-check-row probe-check-${item.status}`}>
                        <div>
                          <strong>{item.label}</strong>
                          <span>{item.details || "-"}</span>
                          {item.remediation ? <em>{item.remediation}</em> : null}
                        </div>
                        <b>{item.status === "pass" ? "通过" : item.status === "warn" ? "提醒" : "失败"}</b>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {deployResult?.steps?.length ? (
                <div className="probe-result-panel">
                  <div className="probe-result-head">
                    <strong>{deployResult.deployed ? "部署完成" : "部署中断"}</strong>
                    <span>{deployResult.message}</span>
                  </div>
                  <div className="probe-check-list">
                    {deployResult.steps.map((item) => (
                      <div key={item.key} className={`probe-check-row probe-check-${item.status}`}>
                        <div>
                          <strong>{item.label}</strong>
                          <span>{item.details || "-"}</span>
                        </div>
                        <b>{item.status === "pass" ? "通过" : "失败"}</b>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </section>

            <section className="admin-panel">
              <div className="admin-panel-head">
                <div>
                  <h2>机器接入状态</h2>
                  <p>等待心跳或外部占用的卡不会进入用户可租卡数。</p>
                </div>
                <strong>{machines.length} 台</strong>
              </div>

              <div className="admin-machine-list">
                {machines.map((machine) => (
                  <article key={machine.cabinet_code} className="admin-machine-row">
                    <div className="machine-main">
                      <strong>{machine.cabinet_code}</strong>
                      <span>{machine.location} · {machine.host_ip}:{machine.ssh_port}</span>
                    </div>
                    <div className="machine-tags">
                      <span>{machine.card_type}</span>
                      <span>{machine.available_cards}/{machine.capacity_cards} 可租</span>
                      <span className={`agent-pill agent-pill-${machine.agent_status}`}>
                        {agentText(machine.agent_status)}
                      </span>
                    </div>
                    <div className="machine-device-strip">
                      {machine.devices.map((device) => (
                        <span key={device.index} className={`device-dot device-dot-${device.observed_status}`}>
                          {device.index} · {observedText(device.observed_status)}
                        </span>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            </section>
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
