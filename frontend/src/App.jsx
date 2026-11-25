import { useEffect, useRef, useState } from "react";
import MetadataGrid from "./components/MetadataGrid";
import StatusPanel from "./components/StatusPanel";
import DeveloperControls from "./components/DeveloperControls";

const API = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
const newSessionId = () => "s-" + crypto.randomUUID().replaceAll("-", "").slice(0, 12);
function errorText(status, body) {
  if (status === 503) return "All configured AI providers are unavailable. This failed request was not saved to history.";
  if (status === 422) { const d = Array.isArray(body?.detail) ? body.detail[0]?.msg : body?.detail; return `Request rejected: ${d || "invalid input"}.`; }
  return typeof body?.detail === "string" ? body.detail : `Request failed (${status}).`;
}
export default function App() {
  const [sessionId] = useState(newSessionId), [items,setItems] = useState([]), [input,setInput] = useState("");
  const [systemPrompt,setSystemPrompt] = useState(""), [simulate,setSimulate] = useState(""), [busy,setBusy] = useState(false), [health,setHealth] = useState(null);
  const endRef = useRef(null);
  useEffect(() => { fetch(`${API}/health`).then(r=>r.json()).then(setHealth).catch(()=>setHealth({status:"offline"})); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({behavior:"smooth"}); }, [items,busy]);
  async function send() {
    const message=input.trim(); if(!message||busy)return; setInput(""); setItems(p=>[...p,{kind:"user",text:message}]); setBusy(true);
    try { const headers={"Content-Type":"application/json"}; if(simulate.trim())headers["X-Simulate-Failure"]=simulate.trim();
      const body={session_id:sessionId,message}; if(systemPrompt.trim())body.system_prompt=systemPrompt.trim();
      const res=await fetch(`${API}/chat`,{method:"POST",headers,body:JSON.stringify(body)}); let data=null; try{data=await res.json()}catch{}
      setItems(p=>[...p,res.ok&&data?.reply?{kind:"assistant",text:data.reply,meta:data.metadata}:{kind:"error",text:errorText(res.status,data)}]);
    } catch { setItems(p=>[...p,{kind:"error",text:"Cannot reach the backend. Confirm FastAPI is running and VITE_API_URL is correct."}]); } finally {setBusy(false)}
  }
  return <div className="shell">
    <aside className="rail">
      <div className="brand"><div className="hazard">// RESILIENT AI SYSTEM</div><h1>FAILSAFE<span>AI</span></h1><p>LLM infrastructure that keeps answering when providers fail.</p></div>
      <StatusPanel health={health}/>
      <section className="session-card"><div className="section-kicker">ACTIVE SESSION</div><code>{sessionId}</code></section>
      <section className="prompt-card"><label htmlFor="sp">SYSTEM BEHAVIOR</label><textarea id="sp" data-testid="system-prompt-input" rows="4" maxLength="4000" value={systemPrompt} onChange={e=>setSystemPrompt(e.target.value)} placeholder="Optional session-level instruction..."/></section>
      <DeveloperControls simulate={simulate} setSimulate={setSimulate}/>
      <div className="rail-footer">FASTAPI / LITELLM / SQLITE <span>v1.0</span></div>
    </aside>
    <main className="workspace">
      <header className="topbar"><div><span className="eyebrow">CONVERSATION TERMINAL</span><h2>Reliable answers. Visible infrastructure.</h2></div><div className="top-status"><i/> SYSTEM ONLINE</div></header>
      <div className="conversation" aria-live="polite">
        {items.length===0 && <div className="hero"><div className="hero-mark">01</div><h3>ASK. ROUTE.<br/><em>RECOVER.</em></h3><p>Send a prompt to start. Every response exposes its model, latency, token usage, cache source and failover route.</p><div className="hero-tags"><span>KEY FAILOVER</span><span>LLM CACHE</span><span>MULTI-TURN</span><span>SQLITE</span></div></div>}
        {items.map((m,i)=> m.kind==="user" ? <div className="message user-message" key={i}><div className="message-label">YOU / {String(i+1).padStart(2,"0")}</div><div className="message-body">{m.text}</div></div> : m.kind==="error" ? <div className="error-card" role="alert" key={i}><b>⚠ PROVIDER ALERT</b><p>{m.text}</p><button type="button" onClick={()=>setInput("Try the request again")}>TRY AGAIN →</button></div> : <div className="message assistant-message" data-testid="assistant-message" key={i}><div className="message-label">FAILSAFE AI / RESPONSE</div><div className="message-body reply">{m.text}</div><MetadataGrid meta={m.meta}/></div>)}
        {busy && <div className="thinking"><span/><span/><span/> ROUTING REQUEST...</div>}<div ref={endRef}/>
      </div>
      <div className="composer-wrap"><div className="composer"><textarea data-testid="chat-input" rows="2" maxLength="4000" value={input} onChange={e=>setInput(e.target.value)} placeholder="Ask FAILSAFE anything..." onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}}}/><div className="composer-actions"><span>{input.length}/4000 · SHIFT+ENTER FOR NEW LINE</span><button data-testid="send-button" onClick={send} disabled={busy||!input.trim()}>{busy?"ROUTING":"SEND →"}</button></div></div></div>
    </main>
  </div>;
}
