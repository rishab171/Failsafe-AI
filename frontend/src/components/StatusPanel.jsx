export default function StatusPanel({ health }) {
  const online = health?.status === "ok";
  return <section className="status-panel">
    <div className="section-kicker">INFRASTRUCTURE</div>
    <div className="status-row"><span>API</span><b className={online ? "ok" : "warn"}>{online ? "● ONLINE" : "● CHECKING"}</b></div>
    <div className="status-row"><span>KEY POOL</span><b>{health?.keys_configured ?? "—"} READY</b></div>
    <div className="status-row"><span>CACHE</span><b className={health?.cache_enabled ? "ok" : "warn"}>{health?.cache_enabled ? "● ENABLED" : "● UNKNOWN"}</b></div>
    <div className="status-row"><span>FAILOVER</span><b className="accent">● ARMED</b></div>
  </section>;
}
