import { formatCurrency } from "../../utils/formatters";

function formatGb(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  const number = Number(value);
  return `${Number.isInteger(number) ? number : number.toFixed(1)} GB`;
}

function selectedTier(option, selectedCardCount) {
  return (option.pricing_preview ?? []).find((tier) => Number(tier.card_count) === selectedCardCount);
}

function machineRows(card) {
  return (card.pricing_options ?? []).flatMap((option) =>
    option.allocation_policy === "spread"
      ? [
          {
            option,
            preferred: false,
            machine: {
              cabinet_code: `${card.card_type}-${option.cabinet_type}-pool`,
              location: "资源池",
              cabinet_type: option.cabinet_type,
              available_cards: option.available_cards,
              managed_cards: option.managed_cards,
              total_cards: option.total_cards,
              available_memory_gb: option.available_memory_gb,
              total_memory_gb: option.total_memory_gb,
              cpu: card.cpu,
              memory: card.memory,
              pool: true
            }
          }
        ]
      : (option.machines ?? []).map((machine) => ({
          option,
          machine,
          preferred: true
        }))
  );
}

export default function CatalogCard({ card, selectedCardCount, onSubmit, submitting }) {
  const rows = machineRows(card);
  const summary = card.summary ?? { available: 0, managed: 0, memory: 0 };

  return (
    <article className="resource-group">
      <div className="resource-group-head">
        <div>
          <span className="resource-group-kicker">{card.cabinet_desc}</span>
          <h2>{card.title}</h2>
        </div>
        <div className="resource-group-stats">
          <span>空闲/总量 <strong>{summary.available}/{summary.managed}</strong></span>
          <span>可用显存 <strong>{formatGb(summary.memory)}</strong></span>
        </div>
      </div>

      <div className="machine-list">
        {rows.length === 0 ? (
          <div className="machine-empty">当前没有可展示的机器资源。</div>
        ) : null}

        {rows.map(({ option, machine, preferred }) => {
          const tier = selectedTier(option, selectedCardCount);
          const canRent =
            !submitting &&
            !option.disabled &&
            Boolean(tier) &&
            Number(machine.available_cards ?? 0) >= selectedCardCount;
          const actionKey = `${card.card_type}-${machine.cabinet_code}`;

          return (
            <div key={machine.cabinet_code} className={`machine-row ${canRent ? "" : "machine-row-muted"}`}>
              <div className="machine-row-top">
                <div>
                  <div className="machine-meta">
                    <span>{machine.location}</span>
                    <span>{machine.pool ? `${card.card_type} 可用资源池` : machine.cabinet_code}</span>
                    <span>{option.cabinet_type}</span>
                  </div>
                  <h3>{card.title} / {card.vram}</h3>
                </div>
                <div className="machine-free-count">
                  空闲/总量 <strong>{machine.available_cards}/{machine.managed_cards || machine.total_cards}</strong>
                </div>
              </div>

              <div className="machine-row-body">
                <div className="machine-spec-column">
                  <span>每GPU分配</span>
                  <p>CPU: <strong>{machine.cpu ?? card.cpu}</strong></p>
                  <p>内存: <strong>{machine.memory ?? card.memory}</strong></p>
                </div>

                <div className="machine-spec-column">
                  <span>显存状态</span>
                  <p>可用显存: <strong>{formatGb(machine.available_memory_gb)}</strong></p>
                  <p>平台可租: <strong>{machine.managed_cards}</strong> 卡，总卡 {machine.total_cards}</p>
                </div>

                <div className="machine-spec-column">
                  <span>隔离方式</span>
                  <p>容器: <strong>独立 SSH</strong></p>
                  <p>设备: 只挂载分配到的卡</p>
                </div>

                <div className="machine-rent-column">
                  <strong className="machine-price">
                    {tier ? `${formatCurrency(tier.hourly_user_price_total)}/时` : "不可租"}
                  </strong>
                  <span>{tier ? `平均 ${formatCurrency(tier.avg_per_card)}/卡·时` : "该数量当前不可用"}</span>
                  <button
                    className="primary-action machine-rent-button"
                    disabled={!canRent}
                    onClick={() =>
                      onSubmit(actionKey, {
                        card_type: card.card_type,
                        cabinet_type: option.cabinet_type,
                        card_count: selectedCardCount,
                        ...(preferred ? { preferred_cabinet_code: machine.cabinet_code } : {})
                      })
                    }
                    type="button"
                  >
                    {submitting ? "提交中..." : canRent ? `${selectedCardCount}卡可租` : "库存不足"}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </article>
  );
}
