export default function PageShell({ children, compact = false }) {
  return (
    <div className={`page-shell ${compact ? "page-shell-compact" : ""}`}>
      <div className="background-orb orb-left" />
      <div className="background-orb orb-right" />
      {children}
    </div>
  );
}
