export default function MetadataGrid({ meta }) {
  const cached = meta.resolution_source === "LLM_CACHE";
  return <div className="metadata-grid">
    <div className={`metric source ${cached ? "cache" : "live"}`}><span>Resolution</span><strong data-testid="meta-source">{meta.resolution_source}</strong></div>
    <div className="metric"><span>Model</span><strong data-testid="meta-model">{meta.model}</strong></div>
    <div className="metric"><span>Latency</span><strong data-testid="meta-latency">{meta.latency_ms} ms</strong></div>
    <div className="metric"><span>Input</span><strong data-testid="meta-input-tokens">{meta.input_tokens}</strong></div>
    <div className="metric"><span>Output</span><strong data-testid="meta-output-tokens">{meta.output_tokens}</strong></div>
    <div className="metric"><span>Route</span><strong>{meta.key_id ?? "CACHE"} / {meta.fallback_attempts} fallback{meta.fallback_attempts === 1 ? "" : "s"}</strong></div>
  </div>;
}
