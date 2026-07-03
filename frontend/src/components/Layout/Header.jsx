import { useSimulationDispatch, useSimulationState } from '../../store/simulationStore';
import { motion } from 'framer-motion';
import { getApiBase } from '../../hooks/useSimulation';

const THREAT_STYLE = {
  LOW:      { label: 'THREAT LOW',      cls: 'bg-blue-500/12 text-blue-200 border-blue-300/30' },
  MEDIUM:   { label: 'THREAT MEDIUM',   cls: 'bg-amber-500/12 text-amber-200 border-amber-300/35' },
  HIGH:     { label: 'THREAT HIGH',     cls: 'bg-red-500/14 text-red-200 border-red-300/40' },
  CRITICAL: { label: 'THREAT CRITICAL', cls: 'bg-red-500/18 text-red-100 border-red-300/50' },
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
  const { spent, budget, telemetry, validatorRuntime, messages, fileSizeBytes, isRunning, scenarioComplete } = useSimulationState();
  const threat = deriveThreat(messages || []);

  // Keep status action-oriented and avoid the old "scan complete" banner.
  const scan = scenarioComplete
    ? { label: 'REPORT READY', cls: 'text-sky-200', dot: 'bg-sky-300', pulse: false }
    : isRunning
    ? { label: 'ANALYZING', cls: 'text-violet-200', dot: 'bg-violet-300', pulse: true }
    : { label: 'READY', cls: 'text-zinc-300', dot: 'bg-zinc-500', pulse: false };

  // Adaptive size label so small APKs don't read "0.00 MB".
  const sizeLabel = (() => {
    const b = Number(fileSizeBytes) || 0;
    if (b <= 0) return '0 KB';
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
    return `${(b / (1024 * 1024)).toFixed(2)} MB`;
  })();

  const spentPct = budget > 0 ? (spent / budget) * 100 : 0;
  const budgetColor = spentPct < 50 ? 'bg-blue-400' : spentPct < 80 ? 'bg-violet-400' : 'bg-red-400';
  const runtime = validatorRuntime || telemetry.validator_runtime || {};
  const runtimeLabel = runtime.label || 'Malware Model Ready';

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
    <header className="relative z-10 shrink-0 px-3 sm:px-4 py-3 glass-surface border-x-0 border-t-0 rounded-none">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-center gap-2.5">
          <svg className="shrink-0 drop-shadow-[0_0_16px_rgba(96,165,250,0.35)]" width="32" height="32" viewBox="0 0 48 48" fill="none" aria-label="logo">
            <defs>
              <linearGradient id="hdrShield" x1="24" y1="3" x2="24" y2="45" gradientUnits="userSpaceOnUse">
                <stop offset="0" stopColor="#1f2937" />
                <stop offset="1" stopColor="#030712" />
              </linearGradient>
              <linearGradient id="hdrScan" x1="14" y1="20" x2="34" y2="30" gradientUnits="userSpaceOnUse">
                <stop offset="0" stopColor="#60a5fa" />
                <stop offset="1" stopColor="#8b5cf6" />
              </linearGradient>
            </defs>
            <path d="M24 3 8 8.5v11.2C8 31 14.7 40.4 24 45c9.3-4.6 16-14 16-25.3V8.5L24 3Z"
                  fill="url(#hdrShield)" stroke="#334155" strokeWidth="1.5" />
            <path d="M14 18.5h20M14 24h20M14 29.5h20" stroke="#1e3a52" strokeWidth="1" />
            <circle cx="22" cy="22" r="7" fill="none" stroke="url(#hdrScan)" strokeWidth="2.4" />
            <path d="M27 27l5 5" stroke="url(#hdrScan)" strokeWidth="2.6" strokeLinecap="round" />
            <circle cx="22" cy="22" r="2.4" fill="#f43f5e" />
          </svg>
          <div className="min-w-0">
            <p className="prism-title text-[11px] sm:text-xs font-semibold uppercase tracking-[0.24em] leading-none">Forensic Console</p>
            <p className="text-[9px] text-zinc-500 leading-none mt-1">Offline · Air-gapped</p>
          </div>
        </div>
      </div>


      <div className="flex flex-wrap items-center gap-2 sm:gap-3 lg:justify-center">
        {/* Threat level — shown when a verdict is detected */}
        {threat && (
          <motion.span
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className={`flex items-center gap-1 text-[10px] forensic-token font-bold px-3 py-2 rounded-xl border bg-[rgba(8,10,16,0.76)] ${threat.cls}`}
          >
            <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M8 1.5 15 14H1L8 1.5Z" />
              <path d="M8 6v3.5M8 11.5v0.5" strokeLinecap="round" />
            </svg>
            {threat.label}
          </motion.span>
        )}

        <div className="bg-[rgba(8,10,16,0.76)] border border-slate-800 rounded-xl px-3 py-2 flex flex-col items-center gap-0.5 min-w-[140px]">
          <div className="flex items-center justify-between w-full">
            <span className="text-[10px] text-zinc-500">FILE SIZE</span>
            <span className="text-[10px] forensic-token text-zinc-200">{sizeLabel}</span>
          </div>
          <div className="w-full h-1 bg-black/50 rounded-full overflow-hidden">
            <motion.div
              className={`h-full ${budgetColor} rounded-full`}
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(spentPct, 100)}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 lg:justify-end min-w-0">
        <button
          onClick={handleClear}
          className="black-button text-[10px] forensic-token px-3 py-2 rounded-xl text-zinc-200 transition-colors"
        >
          Clear
        </button>
        <span className="bg-[rgba(8,10,16,0.76)] border border-slate-800 text-[10px] forensic-token px-3 py-2 rounded-xl text-blue-100 whitespace-nowrap max-w-[190px] truncate">
          {runtimeLabel}
        </span>
        <span className="bg-[rgba(8,10,16,0.76)] border border-slate-800 hidden lg:inline-block text-[10px] forensic-token px-3 py-2 rounded-xl text-sky-300 whitespace-nowrap">
          VaultAgent 3.1 8B
        </span>
        <span className="hidden 2xl:inline text-[9px] text-zinc-600 whitespace-nowrap">4-bit QLoRA · GGUF · Local</span>
      </div>
      </div>
    </header>
  );
}
