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
  return (card.pricing_options ?? [])
    .flatMap((option) =>
      (option.machines ?? []).map((machine) => ({
        option,
        machine
      }))
    )
    .sort((left, right) => {
      const availableDiff = Number(right.machine.available_cards ?? 0) - Number(left.machine.available_cards ?? 0);
      if (availableDiff !== 0) {
        return availableDiff;
      }
      return String(left.machine.cabinet_code).localeCompare(String(right.machine.cabinet_code));
    });
}

function rentButtonText(canRent, submitting, selectedCardCount, availableCards) {
  if (submitting) {
    return "提交中...";
  }
  if (canRent) {
    return `${selectedCardCount}卡可租`;
  }
  return Number(availableCards ?? 0) > 0 ? "该机不足" : "已占用";
}

export default function CatalogCard({ card, selectedCardCount, onSubmit, submittingKey }) {
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
          <div className="machine-empty">当前没有可展示的物理机资源。</div>
        ) : null}

        {rows.map(({ option, machine }) => {
          const tier = selectedTier(option, selectedCardCount);
          const availableCards = Number(machine.available_cards ?? 0);
          const actionKey = `${card.card_type}-${machine.cabinet_code}`;
          const isSubmitting = submittingKey === actionKey;
          const canRent =
            !isSubmitting &&
            !option.disabled &&
            Boolean(tier) &&
            availableCards >= selectedCardCount;
          const managedCards = Number(machine.managed_cards || machine.total_cards || 0);

          return (
            <div key={machine.cabinet_code} className={`machine-row ${canRent ? "" : "machine-row-muted"}`}>
              <div className="machine-row-top">
                <div>
                  <div className="machine-meta">
                    <span>{machine.location}</span>
                    <span>{machine.cabinet_code}</span>
                    <span>{machine.host_ip}</span>
                  </div>
                  <h3>{card.title} / {card.vram}</h3>
                </div>
                <div className="machine-free-count">
                  空闲/总量 <strong>{availableCards}/{managedCards}</strong>
                </div>
              </div>

              <div className="machine-row-body">
                <div className="machine-spec-column">
                  <span>每GPU分配</span>
                  <p>CPU: <strong>{machine.cpu ?? card.cpu}</strong></p>
                  <p>内存: <strong>{machine.memory ?? card.memory}</strong></p>
                </div>

                <div className="machine-spec-column">
                  <span>物理机资源</span>
                  <p>可用显存: <strong>{formatGb(machine.available_memory_gb)}</strong></p>
                  <p>平台可租: <strong>{machine.managed_cards}</strong> 卡，总卡 {machine.total_cards}</p>
                </div>

                <div className="machine-spec-column">
                  <span>交付方式</span>
                  <p>SSH: <strong>1 个独立容器</strong></p>
                  <p>设备: 只挂载本机分配到的卡</p>
                </div>

                <div className="machine-rent-column">
                  <strong className="machine-price">
                    {tier ? `${formatCurrency(tier.hourly_user_price_total)}/小时` : "不可租"}
                  </strong>
                  <span>{tier ? `平均 ${formatCurrency(tier.avg_per_card)}/卡·小时` : "该数量当前不可用"}</span>
                  <button
                    className="primary-action machine-rent-button"
                    disabled={!canRent}
                    onClick={() =>
                      onSubmit(actionKey, {
                        card_type: card.card_type,
                        cabinet_type: option.cabinet_type,
                        card_count: selectedCardCount,
                        preferred_cabinet_code: machine.cabinet_code
                      })
                    }
                    type="button"
                  >
                    {rentButtonText(canRent, isSubmitting, selectedCardCount, availableCards)}
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
