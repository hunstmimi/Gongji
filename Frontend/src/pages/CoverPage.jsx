import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import HeaderUserSection from "../components/layout/HeaderUserSection";
import PageShell from "../components/layout/PageShell";
import NetworkGraph from "../components/cover/NetworkGraph";
import { useAuth } from "../context/AuthContext";
import { getLocationsSummary } from "../services/api";

export default function CoverPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [summaryError, setSummaryError] = useState("");

  useEffect(() => {
    let active = true;
    getLocationsSummary()
      .then((data) => {
        if (active) {
          setSummary(data);
        }
      })
      .catch((err) => {
        if (active) {
          setSummaryError(err.message);
        }
      })
      .finally(() => {
        if (active) {
          setLoadingSummary(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <PageShell>
      <header className="hero-header">
        <div>
          <span className="eyebrow">Compute Rental Network</span>
          <h1>整机柜算力网络</h1>
          <p className="hero-copy">
            实时展示四个位置的机柜分布与可用状态。绿色表示当前仍有可租机柜，红色表示已占满，灰色表示离线省电中。
          </p>
        </div>
        <div className="header-action-group">
          <button className="primary-action" onClick={() => navigate(isAuthenticated ? "/catalog" : "/auth")}>
            立即租赁
          </button>
          <HeaderUserSection />
        </div>
      </header>

      <section className="cover-content cover-content-full">
        <div className="panel panel-network">
          <div className="panel-head">
            <div>
              <h2>可用机柜</h2>
              <p>移动到任意位置节点上，查看该位置内部不同机柜类型的剩余台数。</p>
            </div>
            <div className="legend">
              <span className="legend-chip legend-available">有卡</span>
              <span className="legend-chip legend-rented">塞满</span>
              <span className="legend-chip legend-offline">离线</span>
            </div>
          </div>

          {summaryError ? <div className="error-banner">{summaryError}</div> : null}
          {loadingSummary ? <div className="empty-state">正在加载机柜状态...</div> : null}
          {!loadingSummary && summary ? <NetworkGraph summary={summary} /> : null}
        </div>
      </section>
    </PageShell>
  );
}
