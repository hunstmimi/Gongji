export function formatCurrency(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  return `¥${Number(value).toFixed(2)}`;
}

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) {
    return "-";
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainSeconds = seconds % 60;
  return `${hours}小时 ${minutes}分钟 ${remainSeconds}秒`;
}
