import { useMemo, useState } from "react";
import { buildCurvePath, getNodeClass, getNodeRadius } from "../../utils/network";

export default function NetworkGraph({ summary }) {
  const [hoveredLocation, setHoveredLocation] = useState(null);

  const graphData = useMemo(() => {
    if (!summary?.items) {
      return { nodes: [], edges: [] };
    }
    const width = 1200;
    const height = 520;
    const totals = summary.items.map((item) => Number(item.total_cabinets) || 0);
    const minCabinets = Math.min(...totals);
    const maxCabinets = Math.max(...totals);
    const nodes = summary.items.map((item) => ({
      ...item,
      x: item.x_ratio * width,
      y: item.y_ratio * height,
      radius: getNodeRadius(item.total_cabinets, minCabinets, maxCabinets)
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
    graphData.nodes.find((item) => item.location === hoveredLocation) ?? graphData.nodes[0] ?? null;

  return (
    <div className="network-stage">
      <svg className="network-svg" viewBox="0 0 1200 520" role="img" aria-label="位置机柜网络图">
        <defs>
          <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="rgba(120, 175, 255, 0.65)" />
            <stop offset="100%" stopColor="rgba(76, 221, 171, 0.35)" />
          </linearGradient>
        </defs>
        {graphData.edges.map((edge) => (
          <path key={`${edge.from}-${edge.to}`} d={edge.path} className="network-edge" />
        ))}
        {graphData.nodes.map((node) => (
          <g
            key={node.location}
            className="network-node"
            onMouseEnter={() => setHoveredLocation(node.location)}
            onFocus={() => setHoveredLocation(node.location)}
            tabIndex={0}
          >
            <circle
              cx={node.x}
              cy={node.y}
              r={node.radius + 12}
              className={`node-glow ${getNodeClass(node.node_status)}`}
            />
            <circle
              cx={node.x}
              cy={node.y}
              r={node.radius}
              className={`node-core ${getNodeClass(node.node_status)}`}
            />
            <text x={node.x} y={node.y + node.radius + 28} textAnchor="middle" className="node-label">
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
              {activeNode.node_status === "available"
                ? "仍可租用"
                : activeNode.node_status === "rented"
                  ? "当前塞满"
                  : "离线省电"}
            </span>
          </div>

          <div className="detail-stats-grid">
            <div><span>总机柜</span><strong>{activeNode.total_cabinets}</strong></div>
            <div><span>可用</span><strong>{activeNode.available_cabinets}</strong></div>
            <div><span>租用中</span><strong>{activeNode.rented_cabinets}</strong></div>
            <div><span>离线中</span><strong>{activeNode.offline_cabinets}</strong></div>
            <div><span>可租卡数</span><strong>{activeNode.available_cards ?? 0}</strong></div>
            <div><span>总卡数</span><strong>{activeNode.total_cards ?? 0}</strong></div>
          </div>

          <div className="detail-breakdown">
            {activeNode.cabinet_breakdown?.map((item) => (
              <div key={`${item.card_type}-${item.cabinet_type}`} className="detail-breakdown-row">
                <div>
                  <strong>{item.card_type}</strong>
                  <span>{item.cabinet_type}</span>
                </div>
                <div className="breakdown-metrics">
                  <span>剩余 {item.available_cabinets}</span>
                  <span>可租卡 {item.available_cards ?? 0}</span>
                  <span>离线中 {item.offline_cabinets}</span>
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
