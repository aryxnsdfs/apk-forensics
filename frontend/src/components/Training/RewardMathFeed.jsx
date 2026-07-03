import { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSimulationState } from '../../store/simulationStore';

const AGENT_COLORS = {
  COMMANDER: 'text-blue-400',
  DETECTIVE: 'text-amber-400',
  CODER:     'text-sky-300',
  THREAT_INTEL: 'text-red-400',
};

const AGENT_LABELS = {
  COMMANDER: 'Verdict Engine',
  DETECTIVE: 'Static Analysis',
  CODER:     'Binary Review',
  THREAT_INTEL: 'Threat Intel',
};

function agentKey(agent) {
  return String(agent || '').toUpperCase();
}

function agentColor(agent) {
  return AGENT_COLORS[agentKey(agent)] || 'text-zinc-300';
}

function agentLabel(agent) {
  return AGENT_LABELS[agentKey(agent)] || String(agent || '');
}

export default function RewardMathFeed() {
  const { rewardFeed, totalReward, scenarioComplete } = useSimulationState();
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [rewardFeed]);

  return (
    <div className="panel-card p-3 flex flex-col h-full min-h-0">
      <div className="relative z-10 flex items-center justify-between mb-3 pb-2 border-b border-white/10">
        <span className="text-[10px] font-bold prism-title uppercase tracking-widest flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-300 animate-pulse" />
          Real-Time Reward Feed
        </span>
        <span className={`black-button text-xs forensic-token font-bold ${totalReward >= 0 ? 'text-blue-200' : 'text-red-300'} px-2 py-0.5 rounded-lg`}>
          Σ {(totalReward >= 0 ? '+' : '') + totalReward.toFixed(2)}
        </span>
      </div>
      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto space-y-1.5 pr-1 scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent"
      >
        {rewardFeed.length > 0 ? (
          <AnimatePresence initial={false}>
            {rewardFeed.map((entry) => (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.15 }}
                className="flex items-start gap-2 py-1.5 border-b border-white/5 last:border-0 min-w-0"
              >
                <span className="text-zinc-700 shrink-0 select-none mt-0.5">↳</span>
                <div className="flex-1 min-w-0 flex flex-col gap-0.5">
                  <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-2">
                    <span className="min-w-0 text-[11px] forensic-token tracking-wide leading-snug">
                      <span className={`font-semibold ${agentColor(entry.agent)}`}>{agentLabel(entry.agent)}</span>
                      <span className="text-zinc-600 font-normal"> ▸ </span>
                      <span className="text-zinc-400 font-normal break-words">{entry.target}</span>
                    </span>
                    <span className={`text-[12px] forensic-token font-bold shrink-0 ${entry.value >= 0 ? 'text-blue-200' : 'text-red-300'}`}>
                      {(entry.value >= 0 ? '+' : '') + entry.value.toFixed(2)}
                    </span>
                  </div>
                  <span className="text-zinc-600 text-[9px] forensic-token">{entry.timestamp}</span>
                </div>
              </motion.div>
            ))}
            {scenarioComplete && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-4 pt-3 border-t border-white/10 bg-blue-500/10 p-2 rounded-xl"
              >
                <span className="text-blue-200 font-bold text-xs">
                  [REPORT READY] Total Σ {(totalReward >= 0 ? '+' : '') + totalReward.toFixed(2)}
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        ) : (
          <div className="h-full w-full flex items-center justify-center">
            <div className="text-center opacity-40">
              <div className="text-zinc-500 text-xs mb-1 font-mono">{'>'} Σ +0.00</div>
              <p className="text-zinc-600 text-[10px] font-mono">Awaiting real reward events...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
