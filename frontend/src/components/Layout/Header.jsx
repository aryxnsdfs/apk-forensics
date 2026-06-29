import { useSimulationDispatch, useSimulationState } from '../../store/simulationStore';
import { motion } from 'framer-motion';
import { getApiBase } from '../../hooks/useSimulation';

const AGENT_DISPLAY = {
  COMMANDER: 'Chief Security Officer',
  DETECTIVE: 'Static Analyst',
  CODER: 'Reverse Engineer',
  THREAT_INTEL: 'Threat Intel',
  MANAGER: 'Coordinator',
  EVALUATOR: 'Validator',
};

const THREAT_STYLE = {
  LOW:      { label: 'THREAT LOW · low danger',        cls: 'bg-emerald-950/50 text-emerald-300 border-emerald-500/40' },
  MEDIUM:   { label: 'THREAT MEDIUM · moderate danger', cls: 'bg-amber-950/50 text-amber-300 border-amber-500/50' },
  HIGH:     { label: 'THREAT HIGH · high danger',       cls: 'bg-red-950/50 text-red-300 border-red-500/50' },
  CRITICAL: { label: 'THREAT CRITICAL · severe danger', cls: 'bg-red-900/70 text-red-200 border-red-500/70' },
};

function deriveThreat(messages) {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const text = `${messages[i]?.m2m || ''} ${messages[i]?.english || ''}`;
    const m = text.match(/THREAT[_\s-]?(LOW|MEDIUM|HIGH|CRITICAL)/i);
    if (m) return THREAT_STYLE[m[1].toUpperCase()];
  }
  return null;
}

export default function Header({ onClearReset }) {
  const dispatch = useSimulationDispatch();
  const { slaRemaining, spent, budget, activeAgents, telemetry, validatorRuntime, messages, fileSizeMb } = useSimulationState();
  const threat = deriveThreat(messages || []);

  const slaMin = Math.floor(slaRemaining / 60);
  const slaSec = Math.floor(slaRemaining % 60);
  const slaColor = slaRemaining > 300 ? 'text-emerald-400' : slaRemaining > 60 ? 'text-amber-400' : 'text-red-500';
  const slaUrgent = slaRemaining <= 60;

  const spentPct = budget > 0 ? (spent / budget) * 100 : 0;
  const budgetColor = spentPct < 50 ? 'bg-emerald-500' : spentPct < 80 ? 'bg-amber-500' : 'bg-red-500';
  const runtime = validatorRuntime || telemetry.validator_runtime || {};
  const runtimeLabel = runtime.label || 'Malware Model Ready';
  const runtimeBadgeClass = runtime.ready
    ? runtime.gpu_metrics_applicable
      ? 'bg-blue-950/40 text-blue-300 border-blue-500/30'
      : 'bg-emerald-950/40 text-emerald-300 border-emerald-500/30'
    : 'bg-red-950/40 text-red-300 border-red-500/30';

  const handleClear = async () => {
    const confirmed = window.confirm('Clear the current live dashboard and reset the session?');
    if (!confirmed) return;

    dispatch({ type: 'CLEAR_SIMULATION' });
    if (onClearReset) onClearReset();
    try {
      await fetch(`${getApiBase()}/api/frontend/clear`, { method: 'POST' });
    } catch (error) {
      console.warn('Failed to clear backend replay state:', error);
    }
  };

  return (
    <header className="flex items-center justify-between px-4 py-2 bg-zinc-900 border-b border-zinc-800 h-14 shrink-0">
      {/* ── Left: Branding ── */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2.5">
          {/* Professional forensic shield logo */}
          <svg width="30" height="30" viewBox="0 0 48 48" fill="none" aria-label="logo">
            <defs>
              <linearGradient id="hdrShield" x1="24" y1="3" x2="24" y2="45" gradientUnits="userSpaceOnUse">
                <stop offset="0" stopColor="#1e293b" />
                <stop offset="1" stopColor="#0f172a" />
              </linearGradient>
              <linearGradient id="hdrScan" x1="14" y1="20" x2="34" y2="30" gradientUnits="userSpaceOnUse">
                <stop offset="0" stopColor="#22d3ee" />
                <stop offset="1" stopColor="#0ea5e9" />
              </linearGradient>
            </defs>
            <path d="M24 3 8 8.5v11.2C8 31 14.7 40.4 24 45c9.3-4.6 16-14 16-25.3V8.5L24 3Z"
                  fill="url(#hdrShield)" stroke="#334155" strokeWidth="1.5" />
            <path d="M14 18.5h20M14 24h20M14 29.5h20" stroke="#1e3a52" strokeWidth="1" />
            <circle cx="22" cy="22" r="7" fill="none" stroke="url(#hdrScan)" strokeWidth="2.4" />
            <path d="M27 27l5 5" stroke="url(#hdrScan)" strokeWidth="2.6" strokeLinecap="round" />
            <circle cx="22" cy="22" r="2.4" fill="#f43f5e" />
          </svg>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-300 leading-none">Forensic Console</p>
            <p className="text-[9px] text-zinc-500 leading-none mt-1">Offline · Air-gapped</p>
          </div>
        </div>

        {/* Active Agents — color-coded by role */}
        <div className="flex items-center gap-1 ml-4 px-2 py-1 rounded-md bg-zinc-800/50">
          {activeAgents.map((a) => {
            const colorMap = {
              COMMANDER: 'bg-blue-900/40 text-blue-400 border-blue-500/30',
              DETECTIVE: 'bg-amber-900/40 text-amber-400 border-amber-500/30',
              CODER: 'bg-emerald-900/40 text-emerald-400 border-emerald-500/30',
              THREAT_INTEL: 'bg-red-900/40 text-red-400 border-red-500/30',
              MANAGER: 'bg-purple-900/40 text-purple-400 border-purple-500/30',
              EVALUATOR: 'bg-pink-900/40 text-pink-400 border-pink-500/30',
              DBA_AGENT: 'bg-emerald-900/40 text-emerald-300 border-emerald-500/30',
              SRE_AGENT: 'bg-cyan-900/40 text-cyan-300 border-cyan-500/30',
              SECURITY_AGENT: 'bg-orange-900/40 text-orange-300 border-orange-500/30',
              COMPLIANCE_AGENT: 'bg-yellow-900/40 text-yellow-300 border-yellow-500/30',
            };
            const cls = colorMap[a] || 'bg-zinc-700 text-zinc-300 border-zinc-600';
            return (
              <span key={a} className={`text-[9px] px-1.5 py-0.5 rounded border font-mono font-semibold ${cls}`}>
                {AGENT_DISPLAY[a] || a}
              </span>
            );
          })}
        </div>
      </div>

      {/* ── Center: SLA Timer + Budget ── */}
      <div className="flex items-center gap-6">
        {/* SLA Timer */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">SLA</span>
          <motion.span
            className={`font-mono text-lg font-bold ${slaColor}`}
            animate={slaUrgent ? { scale: [1, 1.05, 1] } : {}}
            transition={{ repeat: Infinity, duration: 1 }}
          >
            {String(slaMin).padStart(2, '0')}:{String(slaSec).padStart(2, '0')}
          </motion.span>
        </div>

        {/* Threat level — shown when a verdict is detected */}
        {threat && (
          <motion.span
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className={`flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${threat.cls}`}
          >
            <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M8 1.5 15 14H1L8 1.5Z" />
              <path d="M8 6v3.5M8 11.5v0.5" strokeLinecap="round" />
            </svg>
            {threat.label}
          </motion.span>
        )}

        {/* Budget */}
        <div className="flex flex-col items-center gap-0.5 min-w-[120px]">
          <div className="flex items-center justify-between w-full">
            <span className="text-[10px] text-zinc-500">FILE SIZE</span>
            <span className="text-[10px] font-mono text-zinc-300">{(Number(fileSizeMb) || 0).toFixed(2)} MB</span>
          </div>
          <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
            <motion.div
              className={`h-full ${budgetColor} rounded-full`}
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(spentPct, 100)}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>
      </div>

      {/* ── Right: Model Badge ── */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleClear}
          className="text-[10px] font-mono px-2 py-1 rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 transition-colors"
        >
          Clear
        </button>
        <span className={`text-[10px] font-mono px-2 py-1 rounded border ${runtimeBadgeClass}`}>
          {runtimeLabel}
        </span>
        <div className="flex flex-col items-end">
          <span className="text-[10px] text-zinc-500">ENGINE</span>
          <span className="text-[10px] font-mono text-cyan-400">
            VaultAgent-Llama-3.1-8B-GRPO
          </span>
          <span className="text-[9px] text-zinc-600">4-bit QLoRA · GGUF · Local</span>
        </div>
        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Model Active" />
      </div>
    </header>
  );
}
