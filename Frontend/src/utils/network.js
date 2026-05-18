export function getNodeRadius(totalCabinets, minCabinets, maxCabinets) {
  const minRadius = 16;
  const maxRadius = 30;
  const total = Number(totalCabinets) || 0;

  if (maxCabinets <= minCabinets) {
    return 22;
  }

  const ratio = (total - minCabinets) / (maxCabinets - minCabinets);
  return Math.round(minRadius + Math.sqrt(Math.max(0, ratio)) * (maxRadius - minRadius));
}

export function getNodeClass(status) {
  return {
    available: "node-available",
    rented: "node-rented",
    offline: "node-offline"
  }[status] ?? "node-offline";
}

export function buildCurvePath(from, to) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const controlOffset = Math.max(50, Math.abs(dx) * 0.18);
  const cp1x = from.x + dx * 0.33;
  const cp1y = from.y - controlOffset;
  const cp2x = from.x + dx * 0.66;
  const cp2y = to.y + controlOffset * (dy > 0 ? 0.35 : -0.35);
  return `M ${from.x} ${from.y} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${to.x} ${to.y}`;
}
