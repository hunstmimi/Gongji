import { useMemo, useState } from "react";
import { buildCurvePath, getNodeClass, getNodeRadius } from "../../utils/network";

function formatGb(value) {
  const number = Number(value ?? 0);
  return `${Number.isInteger(number) ? number : number.toFixed(1)} GB`;
}

function statusText(status) {
  if (status === "available") {
    return "仍可租用";
  }
  if (status === "rented") {
    return "当前塞满";
  }
  return "离线/不可调度";
}

export default function NetworkGraph({ summary }) {
  const [activeLocation, setActiveLocation] = useState(null);

  const graphData = useMemo(() => {
    if (!summary?.items) {
      return { nodes: [], edges: [] };
    }
    const width = 1200;
    const height = 520;
    const totals = summary.items.map((item) => Number(item.total_cards) || Number(item.total_cabinets) || 0);
    const minCards = Math.min(...totals);
    const maxCards = Math.max(...totals);
    const nodes = summary.items.map((item) => ({
      ...item,
      x: item.x_ratio * width,
      y: item.y_ratio * height,
      radius: getNodeRadius(item.total_cards ?? item.total_cabinets, minCards, maxCards)
    }));
    const nodeMap = new Map(nodes.map((item) => [item.location, item]));
    const edges = (summary.edges ?? [])
      .map((edge) => {
        const from = nodeMap.get(edge.from);
        const to = nodeMap.get(edge.to);
        if (!from || !to) {
          return null;
        }
        return { ...edge, path: buildCurvePath(from, to) };
      })
      .filter(Boolean);
    return { nodes, edges };
  }, [summary]);

  const activeNode =
    graphData.nodes.find((item) => item.location === activeLocation) ?? graphData.nodes[0] ?? null;

  return (
    <div className="network-stage">
      <svg className="network-svg" viewBox="0 0 1200 520" role="img" aria-label="位置机柜网络图">
        <defs>
          <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="rgba(61, 151, 207, 0.68)" />
            <stop offset="100%" stopColor="rgba(42, 190, 139, 0.48)" />
          </linearGradient>
        </defs>
        {graphData.edges.map((edge) => (
          <path key={`${edge.from}-${edge.to}`} d={edge.path} className="network-edge" />
        ))}
        {graphData.nodes.map((node) => (
          <g
            key={node.location}
            className={`network-node ${activeNode?.location === node.location ? "network-node-active" : ""}`}
            onMouseEnter={() => setActiveLocation(node.location)}
            onClick={() => setActiveLocation(node.location)}
            onFocus={() => setActiveLocation(node.location)}
            tabIndex={0}
          >
            <circle
              cx={node.x}
              cy={node.y}
              r={node.radius + 16}
              className={`node-glow ${getNodeClass(node.node_status)}`}
            />
            <circle
              cx={node.x}
              cy={node.y}
              r={node.radius}
              className={`node-core ${getNodeClass(node.node_status)}`}
            />
            <text x={node.x} y={node.y + 5} textAnchor="middle" className="node-count-label">
              {node.available_cards}/{node.managed_cards}
            </text>
            <text x={node.x} y={node.y + node.radius + 30} textAnchor="middle" className="node-label">
              {node.location}
            </text>
          </g>
        ))}
      </svg>

      {activeNode ? (
        <aside className="node-detail-card">
          <div className="node-detail-top">
            <div>
              <span className="detail-overline">位置详情</span>
              <h3>{activeNode.location}</h3>
            </div>
            <span className={`detail-status ${getNodeClass(activeNode.node_status)}`}>
              {statusText(activeNode.node_status)}
            </span>
          </div>

          <div className="detail-stats-grid">
            <div><span>总机柜</span><strong>{activeNode.total_cabinets}</strong></div>
            <div><span>可租机柜</span><strong>{activeNode.available_cabinets}</strong></div>
            <div><span>占用中</span><strong>{activeNode.rented_cabinets}</strong></div>
            <div><span>离线/空闲</span><strong>{activeNode.offline_cabinets}</strong></div>
            <div><span>可租卡数</span><strong>{activeNode.available_cards ?? 0}</strong></div>
            <div><span>受管卡数</span><strong>{activeNode.managed_cards ?? 0}</strong></div>
          </div>

          <div className="detail-memory-strip">
            <span>可用显存</span>
            <strong>{formatGb(activeNode.available_memory_gb)}</strong>
            <em>总显存 {formatGb(activeNode.total_memory_gb)}</em>
          </div>

          <div className="detail-breakdown">
            {activeNode.cabinet_breakdown?.map((item) => (
              <div key={`${item.card_type}-${item.cabinet_type}`} className="detail-breakdown-row detail-breakdown-row-rich">
                <div className="breakdown-main">
                  <strong>{item.card_type}</strong>
                  <span>{item.cabinet_type} · 每柜 {item.capacity_cards} 卡</span>
                  <p>
                    剩余机柜 {item.available_cabinets} · 可租卡 {item.available_cards ?? 0} ·
                    可用显存 {formatGb(item.available_memory_gb)}
                  </p>
                </div>
                <div className="breakdown-metrics">
                  <span>占用 {item.active_cards ?? 0}</span>
                  <span>受管 {item.managed_cards ?? 0}</span>
                  <span>总数 {item.total_cabinets}</span>
                </div>
              </div>
            ))}
          </div>
        </aside>
      ) : null}
    </div>
  );
}
