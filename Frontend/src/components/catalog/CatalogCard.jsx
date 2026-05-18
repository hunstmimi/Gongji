import { useEffect, useMemo, useState } from "react";

function clampCardCount(value, min, max) {
  return Math.min(Math.max(value, min), Math.max(min, max));
}

export default function CatalogCard({ card, onSubmit, submitting }) {
  const pricingOptions = useMemo(() => card.pricing_options ?? [], [card.pricing_options]);
  const firstOption = pricingOptions[0] ?? null;
  const [cabinetType, setCabinetType] = useState(firstOption?.cabinet_type ?? card.cabinet_desc);
  const [cardCount, setCardCount] = useState(firstOption?.min_card_count ?? 1);
  const [pricingOpen, setPricingOpen] = useState(false);

  const selectedOption =
    pricingOptions.find((item) => item.cabinet_type === cabinetType) ??
    firstOption;
  const allSelectedPricing = selectedOption?.pricing_preview ?? [];
  const minCardCount = selectedOption?.min_card_count ?? allSelectedPricing[0]?.card_count ?? 1;
  const maxCardCount =
    selectedOption?.max_card_count ??
    allSelectedPricing[allSelectedPricing.length - 1]?.card_count ??
    minCardCount;
  const selectedPricing = allSelectedPricing.filter(
    (tier) => tier.card_count >= minCardCount && tier.card_count <= maxCardCount
  );
  const disabled = submitting || !selectedOption || selectedOption.disabled || maxCardCount < minCardCount;

  useEffect(() => {
    const nextType = firstOption?.cabinet_type ?? card.cabinet_desc;
    setCabinetType(nextType);
    setCardCount(firstOption?.min_card_count ?? 1);
    setPricingOpen(false);
  }, [card.card_type, card.cabinet_desc, firstOption?.cabinet_type, firstOption?.min_card_count]);

  useEffect(() => {
    setCardCount((current) => clampCardCount(current, minCardCount, maxCardCount));
  }, [minCardCount, maxCardCount]);

  useEffect(() => {
    setPricingOpen(false);
    setCardCount(minCardCount);
  }, [cabinetType, minCardCount]);

  return (
    <article className="catalog-card">
      <div className="catalog-card-head">
        <div className="catalog-card-head-top">
          <div>
            <span className="eyebrow">{selectedOption?.capacity_cards > 1 ? "多卡机柜" : "按卡租用"}</span>
            <h3>{card.title}</h3>
          </div>
          <button
            className="primary-action catalog-card-submit"
            disabled={disabled}
            onClick={() =>
              onSubmit(card.card_type, {
                card_type: card.card_type,
                cabinet_type: selectedOption?.cabinet_type ?? cabinetType,
                card_count: cardCount
              })
            }
          >
            {submitting ? "提交中..." : "立即使用"}
          </button>
        </div>
        <p>{card.cabinet_desc}</p>
      </div>

      <div className="spec-list">
        <div><span>显存</span><strong>{card.vram}</strong></div>
        <div><span>CPU</span><strong>{card.cpu}</strong></div>
        <div><span>内存</span><strong>{card.memory}</strong></div>
      </div>

      <div className="card-form">
        {pricingOptions.length > 1 ? (
          <label className="field">
            <span>机柜类型</span>
            <select value={selectedOption?.cabinet_type ?? cabinetType} onChange={(event) => setCabinetType(event.target.value)}>
              {pricingOptions.map((option) => (
                <option key={option.cabinet_type} value={option.cabinet_type} disabled={option.disabled}>
                  {option.cabinet_type}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <label className="field">
          <span>租几张卡</span>
          <input
            type="number"
            min={minCardCount}
            max={maxCardCount}
            value={cardCount}
            disabled={disabled}
            onChange={(event) => {
              const nextValue = Number(event.target.value) || minCardCount;
              setCardCount(clampCardCount(nextValue, minCardCount, maxCardCount));
            }}
          />
        </label>

        {selectedOption ? (
          <div className="readonly-value">
            可租 {selectedOption.available_cards} 卡，本次最多 {maxCardCount} 卡，{selectedOption.capacity_cards} 卡/机柜
            {selectedOption.min_card_count > 1 ? `，${selectedOption.min_card_count} 卡起租` : ""}
          </div>
        ) : null}
      </div>

      <div className="pricing-dropdown">
        <button
          type="button"
          className="pricing-dropdown-trigger"
          onClick={() => setPricingOpen((current) => !current)}
        >
          <span>查看每张卡价位</span>
          <strong>{pricingOpen ? "收起" : `${selectedPricing.length}档价格`}</strong>
        </button>
        {pricingOpen ? (
          <div className="pricing-preview">
            {selectedPricing.map((tier) => (
              <div key={`${selectedOption?.cabinet_type ?? cabinetType}-${tier.card_count}`} className="pricing-preview-row">
                <span>{tier.card_count}卡</span>
                <strong>{tier.hourly_user_price_total.toFixed(1)}元/小时</strong>
                <em>均价 {tier.avg_per_card.toFixed(2)}/卡</em>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      <div className="catalog-card-foot">
        <div>
          <span className="price-label">展示价格</span>
          <strong>{selectedPricing[0] ? `${selectedPricing[0].card_count}卡 ${selectedPricing[0].hourly_user_price_total.toFixed(1)}元/小时起` : card.display_price}</strong>
        </div>
      </div>
    </article>
  );
}
