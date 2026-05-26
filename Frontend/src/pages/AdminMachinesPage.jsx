import { useEffect, useState } from "react";
import AdminShell from "../components/admin/AdminShell";
import {
  createAdminMachine,
  deployAdminMachineAgent,
  getAdminMachines,
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

export default function AdminMachinesPage() {
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

  const loadMachines = () => {
    setError("");
    setLoading(true);
    getAdminMachines()
      .then((data) => {
        setMachineData(data);
      })
      .catch((err) => {
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    loadMachines();
  }, []);

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

  const machinePayload = () => ({
    cabinet_code: form.cabinet_code,
    location: form.location,
    host_ip: form.host_ip,
    ssh_port: Number(form.ssh_port),
    card_type: form.card_type,
    cabinet_type: form.cabinet_type,
    capacity_cards: Number(form.capacity_cards),
    day_hourly_power_cost: Number(form.day_hourly_power_cost),
    night_hourly_power_cost: Number(form.night_hourly_power_cost)
  });

  const accessPayload = () => ({
    ...machinePayload(),
    ssh_username: form.ssh_username,
    ssh_password: form.ssh_password,
    sudo_password: form.sudo_password
  });

  const submitMachine = (event) => {
    event.preventDefault();
    setCreating(true);
    setError("");
    setMachineMessage("");
    createAdminMachine(machinePayload())
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
    <AdminShell
      title="机器管理"
      description="新增机器、检测运行环境、部署节点 Agent，并查看所有接入机器的卡位状态。"
    >
      {error ? <div className="error-banner">{error}</div> : null}
      {machineMessage ? <div className="success-banner">{machineMessage}</div> : null}
      {loading ? <div className="empty-state">正在加载机器数据...</div> : null}

      {!loading && machineData ? (
        <div className="admin-layout">
          <div className="admin-summary-grid">
            <div className="admin-metric">
              <span>接入机器</span>
              <strong>{machineData.summary.total_machines}</strong>
              <em>已登记机器总数</em>
            </div>
            <div className="admin-metric">
              <span>Agent 在线</span>
              <strong>{machineData.summary.online_agents}</strong>
              <em>持续上报心跳</em>
            </div>
            <div className="admin-metric">
              <span>可租卡数</span>
              <strong>{machineData.summary.available_cards}</strong>
              <em>当前可调度卡位</em>
            </div>
            <div className="admin-metric">
              <span>不可租卡</span>
              <strong>{machineData.summary.blocked_cards}</strong>
              <em>外部占用或异常</em>
            </div>
          </div>

          <div className="admin-content-grid admin-machine-grid">
            <section className="admin-panel">
              <div className="admin-panel-head">
                <div>
                  <h2>添加新机器</h2>
                  <p>检测通过后可一键部署 Agent；只录入机器时会等待后续心跳，不会立即误售。</p>
                </div>
              </div>

              <form className="admin-machine-form" onSubmit={submitMachine}>
                <label>
                  <span>机器编号</span>
                  <input value={form.cabinet_code} onChange={(event) => updateField("cabinet_code", event.target.value)} placeholder="例如 10.20.12.230-4090" required />
                </label>
                <label>
                  <span>机器 IP</span>
                  <input value={form.host_ip} onChange={(event) => updateField("host_ip", event.target.value)} placeholder="10.20.12.230" required />
                </label>
                <label>
                  <span>位置</span>
                  <input list="admin-locations" value={form.location} onChange={(event) => updateField("location", event.target.value)} required />
                  <datalist id="admin-locations">
                    {locations.map((item) => (
                      <option key={item} value={item} />
                    ))}
                  </datalist>
                </label>
                <label>
                  <span>SSH 端口</span>
                  <input type="number" min="1" max="65535" value={form.ssh_port} onChange={(event) => updateField("ssh_port", event.target.value)} required />
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
                  <input type="number" min="1" max="16" value={form.capacity_cards} onChange={(event) => updateField("capacity_cards", event.target.value)} required />
                </label>
                <label>
                  <span>白天电费成本/小时</span>
                  <input type="number" min="0" step="0.1" value={form.day_hourly_power_cost} onChange={(event) => updateField("day_hourly_power_cost", event.target.value)} required />
                </label>
                <label>
                  <span>夜间电费成本/小时</span>
                  <input type="number" min="0" step="0.1" value={form.night_hourly_power_cost} onChange={(event) => updateField("night_hourly_power_cost", event.target.value)} required />
                </label>
                <label>
                  <span>SSH 用户名</span>
                  <input value={form.ssh_username} onChange={(event) => updateField("ssh_username", event.target.value)} placeholder="testsv" autoComplete="username" />
                </label>
                <label>
                  <span>SSH 密码</span>
                  <input type="password" value={form.ssh_password} onChange={(event) => updateField("ssh_password", event.target.value)} placeholder="仅本次检测/部署使用" autoComplete="current-password" />
                </label>
                <label className="admin-machine-wide">
                  <span>sudo 密码</span>
                  <input type="password" value={form.sudo_password} onChange={(event) => updateField("sudo_password", event.target.value)} placeholder="不填则默认同 SSH 密码" autoComplete="current-password" />
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
        </div>
      ) : null}
    </AdminShell>
  );
}
