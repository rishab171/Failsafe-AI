const presets = [
  ["", "NO FAILURE"], ["key_1=429", "KEY 1 → 429"], ["key_1=500", "KEY 1 → 500"], ["*=429", "ALL KEYS → 429"]
];
export default function DeveloperControls({ simulate, setSimulate }) {
  return <details className="dev-controls">
    <summary>DEVELOPER CONTROLS <span>+</span></summary>
    <p>Failure simulation is request-scoped and exists for the assessment demo.</p>
    <div className="preset-grid">{presets.map(([value,label]) => <button key={label} type="button" className={simulate === value ? "selected" : ""} onClick={() => setSimulate(value)}>{label}</button>)}</div>
    <label htmlFor="sim">Custom header value</label>
    <input id="sim" value={simulate} onChange={e => setSimulate(e.target.value)} placeholder="key_1=429,key_2=500" />
  </details>;
}
