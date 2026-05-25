import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import CatalogCard from "../components/catalog/CatalogCard";
import HeaderUserSection from "../components/layout/HeaderUserSection";
import PageShell from "../components/layout/PageShell";
import { createRental, getCards } from "../services/api";

function summarizeCard(card) {
  const options = card.pricing_options ?? [];
  return options.reduce(
    (summary, option) => ({
      available: summary.available + Number(option.available_cards ?? 0),
      managed: summary.managed + Number(option.managed_cards ?? option.total_cards ?? 0),
      memory: summary.memory + Number(option.available_memory_gb ?? 0),
      max: Math.max(summary.max, Number(option.max_card_count ?? 1))
    }),
    { available: 0, managed: 0, memory: 0, max: 1 }
  );
}

function getCountOptions(cards, selectedType) {
  const relevantCards = selectedType === "all" ? cards : cards.filter((card) => card.card_type === selectedType);
  const maxCount = Math.max(
    1,
    ...relevantCards.flatMap((card) =>
      (card.pricing_options ?? []).map((option) => Number(option.max_card_count ?? 1))
    )
  );
  return Array.from({ length: Math.min(maxCount, 12) }, (_, index) => index + 1);
}

export default function CatalogPage() {
  const navigate = useNavigate();
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submittingCardKey, setSubmittingCardKey] = useState("");
  const [selectedType, setSelectedType] = useState("all");
  const [selectedCardCount, setSelectedCardCount] = useState(1);

  useEffect(() => {
    let active = true;
    getCards()
      .then((data) => {
        if (active) {
          setCards(data.items ?? []);
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
  }, []);

  const cardStats = useMemo(
    () => cards.map((card) => ({ ...card, summary: summarizeCard(card) })),
    [cards]
  );
  const filteredCards = selectedType === "all"
    ? cardStats
    : cardStats.filter((card) => card.card_type === selectedType);
  const countOptions = useMemo(() => getCountOptions(cards, selectedType), [cards, selectedType]);
  const totalSummary = cardStats.reduce(
    (summary, card) => ({
      available: summary.available + card.summary.available,
      managed: summary.managed + card.summary.managed
    }),
    { available: 0, managed: 0 }
  );

  useEffect(() => {
    if (!countOptions.includes(selectedCardCount)) {
      setSelectedCardCount(countOptions[0] ?? 1);
    }
  }, [countOptions, selectedCardCount]);

  async function handleCreateRental(cardKey, payload) {
    setSubmittingCardKey(cardKey);
    setError("");
    try {
      const result = await createRental(payload);
      navigate(`/result?rentalId=${result.rental_id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmittingCardKey("");
    }
  }

  return (
    <PageShell compact>
      <header className="standard-header catalog-standard-header">
        <div>
          <span className="eyebrow">Compute Market</span>
          <h1>选择可用算力</h1>
          <p>按卡型和卡数筛选当前可租资源。点击某台机器或资源池的租赁按钮后，后端会锁定对应卡并创建独立 SSH 容器。</p>
        </div>
        <div className="header-action-group">
          <Link className="secondary-link" to="/">
            返回算力网络
          </Link>
          <HeaderUserSection />
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      {loading ? (
        <div className="empty-state">正在加载卡型与机器资源...</div>
      ) : (
        <>
          <section className="rental-filter-panel">
            <div className="filter-summary-strip">
              <div>
                <span>平台空闲卡数</span>
                <strong>{totalSummary.available}</strong>
                <em>/ {totalSummary.managed}</em>
              </div>
              <p>空闲统计会排除已禁用、未知占用和健康异常的设备。</p>
            </div>

            <div className="filter-row">
              <span className="filter-label">GPU型号:</span>
              <div className="filter-chip-wrap">
                <button
                  className={`filter-check-chip ${selectedType === "all" ? "filter-check-chip-active" : ""}`}
                  onClick={() => setSelectedType("all")}
                  type="button"
                >
                  <span className="filter-check-box" />
                  全部 ({totalSummary.available}/{totalSummary.managed})
                </button>
                {cardStats.map((card) => (
                  <button
                    key={card.card_type}
                    className={`filter-check-chip ${selectedType === card.card_type ? "filter-check-chip-active" : ""}`}
                    onClick={() => setSelectedType(card.card_type)}
                    type="button"
                  >
                    <span className="filter-check-box" />
                    {card.title} ({card.summary.available}/{card.summary.managed})
                  </button>
                ))}
              </div>
            </div>

            <div className="filter-row">
              <span className="filter-label">GPU数量:</span>
              <div className="count-segment">
                {countOptions.map((count) => (
                  <button
                    key={count}
                    className={selectedCardCount === count ? "count-segment-active" : ""}
                    onClick={() => setSelectedCardCount(count)}
                    type="button"
                  >
                    {count}
                  </button>
                ))}
              </div>
            </div>
          </section>

          <section className="catalog-resource-list">
            {filteredCards.map((card) => (
              <CatalogCard
                key={card.card_type}
                card={card}
                selectedCardCount={selectedCardCount}
                onSubmit={handleCreateRental}
                submitting={submittingCardKey === card.card_type}
              />
            ))}
          </section>
        </>
      )}
    </PageShell>
  );
}
