import { motion } from 'framer-motion';
import { useSimulationState } from '../../store/simulationStore';

function TimelineCard({ title, dotClass, borderClass, bgClass, metrics, progressClass, progressPct }) {
  return (
    <div className={`glass-inset rounded-2xl ${borderClass} ${bgClass} p-3 flex flex-col gap-3 min-w-0`}>
      <div className="flex items-center gap-1.5">
        <span className={`w-2 h-2 rounded-full ${dotClass}`} />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-200">{title}</span>
      </div>

      <div className="space-y-2">
        {metrics.map((metric) => (
          <div key={metric.label} className="flex items-start justify-between gap-3">
            <span className="text-[10px] text-zinc-500 shrink-0">{metric.label}</span>
            <span className={`min-w-0 text-[11px] forensic-token text-right break-all ${metric.valueClass}`}>
              {metric.value}
            </span>
          </div>
        ))}
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between text-[10px] text-zinc-500">
          <span>Execution Track</span>
          <span className="font-mono">{progressPct}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-black/50 overflow-hidden">
          <motion.div
            className={`h-full ${progressClass}`}
            initial={{ width: 0 }}
            animate={{ width: `${progressPct}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          />
        </div>
      </div>
    </div>
  );
}

export default function DeadTimeline() {
  const { counterfactual, spent, budget, elapsedMs, telemetry, scenarioComplete, isRunning } = useSimulationState();
  const liveSeconds = Math.max(1, Math.floor(elapsedMs / 1000));
  const liveSpent = Number(spent || 0);

  const normalizeMetric = (value, fallback) => {
    if (typeof value !== 'string') return value ?? fallback;
    return value.includes('...') ? fallback : value;
  };

  const actual = counterfactual?.actual || {
    time: `${liveSeconds}s`,
    cost: `$${liveSpent.toFixed(3)}`,
    sla: telemetry.sla_remaining_seconds > 0 ? 'SAFE' : 'BREACHED',
    outcome: scenarioComplete ? 'RESOLVED' : 'COMPUTING...',
  };

  const dead = counterfactual?.dead || {
    time: `${Math.max(10, Math.floor(liveSeconds * 2.4) || 18)}s`,
    cost: `$${Math.max(liveSpent * 4.5, 0.25).toFixed(2)}`,
    sla: 'BREACHED',
    outcome: scenarioComplete ? 'MANUAL_ESCALATION' : 'PROJECTING FALLBACK...',
  };

  const showPlaceholder = !isRunning && !scenarioComplete && !counterfactual;

  const actualPct = Math.max(8, Math.min(100, budget > 0 ? Math.round((liveSpent / budget) * 100) : 0));
  const deadPct = Math.max(actualPct + 18, 72);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="panel-card p-3 flex flex-col"
    >
      <div className="relative z-10 flex items-center justify-between mb-3">
        <span className="text-[10px] font-bold prism-title uppercase tracking-widest flex items-center gap-1.5">
          <span className="w-1 h-3 bg-blue-300 rounded-full" />
          Analysis Efficiency
        </span>
        <span className="text-[9px] forensic-token text-zinc-600">
          {showPlaceholder ? 'waiting' : counterfactual ? 'live comparison ready' : 'tracking live estimate'}
        </span>
      </div>

      {showPlaceholder ? (
        <div className="relative z-10 h-32 flex items-center justify-center glass-inset rounded-2xl">
          <p className="text-[10px] text-zinc-600 forensic-token italic">Awaiting scenario execution...</p>
        </div>
      ) : (
        <div className="relative z-10 grid grid-cols-1 xl:grid-cols-2 gap-2">
          <TimelineCard
          title="VaultAgent (Automated)"
          dotClass="bg-blue-300"
          borderClass="border-blue-300/20 shadow-[0_0_18px_-5px_rgba(96,165,250,0.22)]"
          bgClass="bg-blue-500/[0.04]"
          progressClass="bg-blue-400"
          progressPct={actualPct}
          metrics={[
            { label: 'Analysis Cost', value: normalizeMetric(actual.cost, `$${liveSpent.toFixed(3)}`), valueClass: 'text-blue-200' },
            { label: 'Time', value: normalizeMetric(actual.time, `${liveSeconds}s`), valueClass: 'text-sky-200' },
            { label: 'Method', value: 'Static · Offline', valueClass: 'text-sky-200' },
            { label: 'Outcome', value: normalizeMetric(actual.outcome, scenarioComplete ? 'REPORT READY' : 'ANALYZING...'), valueClass: 'text-blue-200 font-bold' },
          ]}
        />

        <TimelineCard
          title="Manual Analyst"
          dotClass="bg-red-500"
          borderClass="border-red-500/20 opacity-60 grayscale-[0.5]"
          bgClass="bg-red-500/[0.03]"
          progressClass="bg-red-500"
          progressPct={Math.min(deadPct, 100)}
          metrics={[
            { label: 'Est. Cost', value: normalizeMetric(dead.cost, `$${Math.max(liveSpent * 4.5, 0.25).toFixed(2)}`), valueClass: 'text-red-400' },
            { label: 'Est. Time', value: normalizeMetric(dead.time, `${Math.max(10, Math.floor(liveSeconds * 2.4))}m`), valueClass: 'text-red-300' },
            { label: 'Method', value: 'Manual reverse-eng', valueClass: 'text-red-300' },
            { label: 'Outcome', value: normalizeMetric(dead.outcome, scenarioComplete ? 'REPORT READY' : 'PENDING...'), valueClass: 'text-red-300 font-bold' },
          ]}
        />
      </div>
      )}
    </motion.div>
  );
}
