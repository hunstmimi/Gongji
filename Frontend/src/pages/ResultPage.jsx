import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import HeaderUserSection from "../components/layout/HeaderUserSection";
import PageShell from "../components/layout/PageShell";
import { cancelRental, getRentalDetail } from "../services/api";
import { formatCurrency, formatDuration } from "../utils/formatters";

export default function ResultPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const rentalId = searchParams.get("rentalId");
  const [rental, setRental] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const [sshReady, setSshReady] = useState(false);

  useEffect(() => {
    if (!rentalId) {
      setError("缺少 rentalId");
      setLoading(false);
      return;
    }
    let active = true;
    getRentalDetail(rentalId)
      .then((data) => {
        if (active) {
          setRental(data);
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
  }, [rentalId]);

  useEffect(() => {
    if (!rentalId || rental?.status !== "active") {
      return undefined;
    }
    const timer = window.setInterval(() => {
      getRentalDetail(rentalId)
        .then((data) => {
          setRental(data);
        })
        .catch(() => {
          window.clearInterval(timer);
        });
    }, 10000);
    return () => window.clearInterval(timer);
  }, [rentalId, rental?.status]);

  useEffect(() => {
    if (!rentalId || rental?.status === "cancelled") {
      setSshReady(false);
      return;
    }
    if (rental?.provisioning_status === "ready") {
      setSshReady(true);
      return;
    }
    setSshReady(false);
    const timer = window.setTimeout(() => {
      setSshReady(true);
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [rentalId, rental?.status, rental?.provisioning_status]);

  async function handleCancelRental() {
    if (!rentalId) {
      return;
    }
    setCancelling(true);
    setError("");
    try {
      const result = await cancelRental(rentalId);
      setRental((current) => (current ? { ...current, ...result, status: result.status } : current));
    } catch (err) {
      setError(err.message);
    } finally {
      setCancelling(false);
    }
  }

  if (!rentalId) {
    return <Navigate to="/catalog" replace />;
  }

  return (
    <PageShell compact>
      <header className="standard-header">
        <div>
          <span className="eyebrow">Rental Result</span>
          <h1>连接信息与分配结果</h1>
          <p>创建租单后即可查看已分配机柜、小时成本、总时长与取消租用状态。</p>
        </div>
        <div className="header-action-group">
          <Link className="secondary-link" to="/catalog">
            返回卡型页
          </Link>
          <HeaderUserSection />
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}
      {loading ? <div className="empty-state">正在加载租单详情...</div> : null}

      {!loading && rental ? (
        <section className="result-layout">
          <div className="panel result-primary result-shell">
            <div className="result-instance-head">
              <div>
                <span className="eyebrow">Instance</span>
                <h2>{rental.card_label}</h2>
                <p>
                  {rental.allocations[0]?.location ?? "-"} · 创建于 {rental.started_at ?? "-"}
                </p>
              </div>
              <div className="result-instance-actions">
                <span className={`detail-status ${rental.status === "active" ? "node-available" : "node-offline"}`}>
                  {rental.status === "active"
                    ? "运行中"
                    : rental.stop_reason === "balance_exhausted"
                      ? "余额耗尽停机"
                      : "已关机"}
                </span>
                <button
                  className="secondary-link"
                  disabled={cancelling || rental.status === "cancelled"}
                  onClick={handleCancelRental}
                >
                  {rental.status === "cancelled" ? "已关机" : cancelling ? "处理中..." : "关机"}
                </button>
              </div>
            </div>

            <div className="result-info-board">
              <div className="result-info-column">
                <span className="result-info-title">规格配置</span>
                <strong>{rental.card_count} x {rental.card_type}</strong>
                <span>{rental.cabinet_type}</span>
                <span>{rental.allocations.length} 台机柜参与分配</span>
              </div>

              <div className="result-info-column">
                <span className="result-info-title">计费方式</span>
                <strong>{formatCurrency(rental.hourly_user_price_total)}/小时</strong>
                <span>{rental.power_cost_label ?? "预估电费成本"} {formatCurrency(rental.hourly_power_cost_total)}/小时</span>
                <span>已运行 {formatDuration(rental.duration_seconds)}</span>
                <span>当前花销 {formatCurrency(rental.user_total_amount)}</span>
              </div>

              <div className="result-info-column result-info-column-ssh">
                <span className="result-info-title">租单连接信息</span>
                {!sshReady && rental.status !== "cancelled" ? (
                  <div className="ssh-loading-card">
                    <strong>正在准备租单环境...</strong>
                    <p>系统正在分配可见设备并生成连接信息。</p>
                  </div>
                ) : (
                  <div className="ssh-plain-block">
                    {(rental.connections?.length ? rental.connections : [rental.connection]).filter(Boolean).map((connection) => (
                      <div key={connection.environment_id ?? connection.cabinet_code ?? connection.ip}>
                        <span>{connection.cabinet_code ? `${connection.cabinet_code} · ${connection.allocated_cards}卡` : "登录账户"}</span>
                        {connection.environment_id ? <span>环境 {connection.environment_id}</span> : null}
                        <strong>{connection.command ?? "-"}</strong>
                        {connection.visible_devices ? <span>可见设备 {connection.visible_devices}</span> : null}
                        <span>登录密码 {connection.password ?? "-"}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="allocation-list">
              {rental.allocations.map((item) => (
                <article key={item.cabinet_code} className="allocation-card">
                  <div>
                    <h3>{item.cabinet_code}</h3>
                    <p>{item.location} · {item.cabinet_type}</p>
                  </div>
                  <div className="allocation-metrics">
                    <span>本次分配 {item.allocated_cards} 卡</span>
                    {item.visible_devices ? <span>可见设备 {item.visible_devices}</span> : null}
                    <span>机柜节点 {item.cabinet_code}</span>
                    <span>用户每小时 {formatCurrency(item.hourly_user_price)}</span>
                    <span>预估电费每小时 {formatCurrency(item.hourly_power_cost)}</span>
                  </div>
                </article>
              ))}
            </div>

            <button className="secondary-link secondary-link-block" onClick={() => navigate("/")}>
              回到封面页
            </button>
          </div>
        </section>
      ) : null}
    </PageShell>
  );
}
