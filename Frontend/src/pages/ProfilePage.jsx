import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import HeaderUserSection from "../components/layout/HeaderUserSection";
import PageShell from "../components/layout/PageShell";
import { useAuth } from "../context/AuthContext";
import { getDashboard, rechargeBalance } from "../services/api";
import { formatCurrency } from "../utils/formatters";

export default function ProfilePage() {
  const navigate = useNavigate();
  const { isAuthenticated, logout, ready, setUser } = useAuth();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("active");
  const [recharging, setRecharging] = useState(false);
  const [rechargeAmount, setRechargeAmount] = useState("");
  const [showRechargeForm, setShowRechargeForm] = useState(false);
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (!ready) {
      return undefined;
    }
    if (!isAuthenticated) {
      setLoading(false);
      setDashboard(null);
      setError("请先登录");
      return undefined;
    }

    let active = true;
    setLoading(true);
    setError("");
    getDashboard()
      .then((data) => {
        if (active) {
          setDashboard(data);
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
  }, [isAuthenticated, ready]);

  async function handleRecharge() {
    const amount = Number(rechargeAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError("请输入大于 0 的充值金额");
      setSuccess("");
      return;
    }
    setRecharging(true);
    setError("");
    setSuccess("");
    try {
      const payload = await rechargeBalance(amount);
      setDashboard((current) =>
        current
          ? {
              ...current,
              user: { ...current.user, balance: payload.balance },
              wallet: { ...current.wallet, balance: payload.balance }
            }
          : current
      );
      setUser((current) => (current ? { ...current, balance: payload.balance } : current));
      setRechargeAmount("");
      setShowRechargeForm(false);
      setSuccess(`充值成功，已到账 ${formatCurrency(amount)}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setRecharging(false);
    }
  }

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  const currentItems = dashboard?.active_rentals ?? [];
  const historyItems = dashboard?.history_rentals ?? [];
  const showingItems = tab === "active" ? currentItems : historyItems;

  return (
    <PageShell compact>
      <header className="standard-header">
        <div>
          <span className="eyebrow">Profile Center</span>
          <h1>我的租赁</h1>
          <p>进行中和历史记录分开展示。进行中的卡片支持直接跳到连接信息与分配结果页面。</p>
        </div>
        <div className="header-action-group">
          <Link className="secondary-link" to="/">
            返回封面页
          </Link>
          <HeaderUserSection />
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}
      {success ? <div className="success-banner">{success}</div> : null}
      {loading ? <div className="empty-state">正在加载个人中心...</div> : null}

      {!loading && dashboard ? (
        <section className="profile-layout">
          <div className="profile-main-panel">
            <div className="profile-main-head">
              <div>
                <h2>我的租赁</h2>
                <p>点进行中查看当前租赁实例，点历史查看过往租单。</p>
              </div>
              <div className="profile-tab-group">
                <button
                  className={`profile-tab-chip ${tab === "active" ? "profile-tab-chip-active" : ""}`}
                  onClick={() => setTab("active")}
                >
                  进行中
                </button>
                <button
                  className={`profile-tab-chip ${tab === "history" ? "profile-tab-chip-active" : ""}`}
                  onClick={() => setTab("history")}
                >
                  历史
                </button>
              </div>
            </div>

            <div className="profile-section-label">{tab === "active" ? "正在租赁" : "租赁历史"}</div>

            <div className="profile-card-list">
              {showingItems.length === 0 ? (
                <div className="profile-empty-card">
                  {tab === "active"
                    ? "当前没有进行中的租赁。等你真正创建租单后，这里会自动出现。"
                    : "当前没有历史租赁记录。"}
                </div>
              ) : null}

              {tab === "active"
                ? showingItems.map((item) => (
                    <button
                      key={item.rental_id}
                      className="profile-rental-card profile-rental-card-button"
                      onClick={() => navigate(`/result?rentalId=${item.rental_id}`)}
                    >
                      <div>
                        <h3>{item.card_label}</h3>
                        <p>
                          单价 {formatCurrency(item.hourly_price)} / 小时
                          <span className="meta-divider">·</span>
                          时长 {item.duration_hours} 小时
                          <span className="meta-divider">·</span>
                          当前花销 {formatCurrency(item.current_amount)}
                        </p>
                      </div>
                      <span className="profile-card-cta">查看连接信息</span>
                    </button>
                  ))
                : showingItems.map((item) => (
                    <article key={item.rental_id} className="profile-rental-card">
                      <div>
                        <h3>{item.card_label}</h3>
                        <p>
                          单价 {formatCurrency(item.hourly_price)} / 小时
                          <span className="meta-divider">·</span>
                          时长 {item.duration_hours} 小时
                          <span className="meta-divider">·</span>
                          总价 {formatCurrency(item.total_amount)}
                        </p>
                      </div>
                      <span className="history-status-tag">
                        {item.stop_reason === "balance_exhausted" ? "余额耗尽" : "已完成"}
                      </span>
                    </article>
                  ))}
            </div>
          </div>

          <aside className="profile-side-panel">
            <div className="profile-side-card">
              <h2>个人信息</h2>
              <strong>{dashboard.user.phone_masked}</strong>
              <span>账户 ID：{dashboard.user.username}</span>
            </div>

            <div className="profile-side-card">
              <h2>余额与充值</h2>
              <span className="balance-caption">账户余额（元）</span>
              <strong className="balance-amount">{dashboard.wallet.balance.toFixed(2)}</strong>
              <div className="pending-card">待结算：{formatCurrency(dashboard.wallet.pending_settlement)}</div>
              {!showRechargeForm ? (
                <button
                  className="primary-action profile-recharge"
                  onClick={() => {
                    setShowRechargeForm(true);
                    setError("");
                    setSuccess("");
                  }}
                >
                  充值
                </button>
              ) : (
                <div className="recharge-panel">
                  <label className="field recharge-field">
                    <span>充值金额</span>
                    <input
                      min="0.01"
                      step="0.01"
                      type="number"
                      value={rechargeAmount}
                      onChange={(event) => setRechargeAmount(event.target.value)}
                      placeholder="请输入充值金额"
                      autoFocus
                    />
                  </label>
                  <div className="recharge-actions">
                    <button className="primary-action profile-recharge" disabled={recharging} onClick={handleRecharge}>
                      {recharging ? "充值中..." : "确认充值"}
                    </button>
                    <button
                      className="secondary-link profile-recharge-cancel"
                      disabled={recharging}
                      onClick={() => {
                        setShowRechargeForm(false);
                        setRechargeAmount("");
                      }}
                    >
                      取消
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="profile-side-card profile-side-card-compact">
              <h2>账户操作</h2>
              <button className="danger-action secondary-link-block" onClick={handleLogout}>
                退出登录
              </button>
            </div>
          </aside>
        </section>
      ) : null}
    </PageShell>
  );
}
