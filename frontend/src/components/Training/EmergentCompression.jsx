import { useSimulationState } from '../../store/simulationStore';

function StatusRow({ label, active, activeText = 'Present', inactiveText = 'Missing' }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-white/10 last:border-b-0">
      <span className="text-[10px] text-zinc-400">{label}</span>
      <span className={`forensic-token text-[10px] font-mono font-semibold ${active ? 'text-sky-200' : 'text-zinc-500'}`}>
        {active ? activeText : inactiveText}
      </span>
    </div>
  );
}

export default function EmergentCompression() {
  const { rejectedRun, chosenRun, rcaDocument, scenarioComplete } = useSimulationState();

  return (
    <div className="glass-surface p-3 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <span className="prism-title text-[10px] font-semibold uppercase tracking-wider">
          Evidence Checklist
        </span>
        <span className={`forensic-token text-[10px] font-mono font-bold ${scenarioComplete ? 'text-sky-200' : 'text-zinc-500'}`}>
          {scenarioComplete ? 'Report Ready' : 'In Progress'}
        </span>
      </div>

      <div className="glass-inset flex-1 min-h-0 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-700 pr-1 rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2 space-y-1">
        <StatusRow label="Rejected baseline sample" active={Boolean(rejectedRun)} activeText="Captured" inactiveText="Not required" />
        <StatusRow label="Passing validator fix" active={Boolean(chosenRun)} />
        <StatusRow label="RCA document generated" active={Boolean(rcaDocument)} />
      </div>

      <div className="pt-2 border-t border-zinc-800 shrink-0">
        <p className="text-[10px] text-zinc-500 leading-relaxed">
          This panel only reflects captured run evidence. It does not infer training progress or fabricate optimization history.
        </p>
      </div>
    </div>
  );
}
