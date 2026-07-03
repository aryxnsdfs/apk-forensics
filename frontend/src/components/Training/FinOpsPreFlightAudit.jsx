import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { useSimulationState } from '../../store/simulationStore';

function toCheckState(value) {
  if (value === true) return 'pass';
  if (value === false) return 'fail';
  return 'pending';
}

function parseStatus(value) {
  const normalized = String(value || '').toUpperCase();
  if (!normalized) return 'pending';
  if (normalized === 'PASS' || normalized === 'STABLE' || normalized === 'RUNNING') return 'pass';
  if (normalized === 'FAIL' || normalized === 'FAILED' || normalized === 'CRITICAL') return 'fail';
  return 'pending';
}

function getRowStyles(state, isFocused) {
  if (state === 'pass') {
    return {
      border: 'border-sky-400/40',
      bg: 'bg-sky-500/10',
      text: 'text-sky-200',
      mark: '✓',
      markClass: 'text-sky-200',
    };
  }
  if (state === 'fail') {
    return {
      border: 'border-red-500/40',
      bg: 'bg-red-500/10',
      text: 'text-red-300',
      mark: '✗',
      markClass: 'text-red-300',
    };
  }
  return {
    border: isFocused ? 'border-blue-400/50' : 'border-white/10',
    bg: isFocused ? 'bg-blue-500/10' : 'bg-white/[0.04]',
    text: isFocused ? 'text-blue-300' : 'text-zinc-400',
    mark: '•',
    markClass: isFocused ? 'text-blue-300' : 'text-zinc-600',
  };
}

export default function FinOpsPreFlightAudit() {
  const {
    rewardFeed,
    telemetry,
    lastValidatorResult,
    chosenRun,
    verdict,
    apkPackage,
    apkPermissionCount,
    apkFileCount,
    fileSizeBytes,
    isRunning,
  } = useSimulationState();

  const [activeStepIdx, setActiveStepIdx] = useState(-1);

  const coderSignal = useMemo(() => {
    for (let i = rewardFeed.length - 1; i >= 0; i -= 1) {
      const agent = String(rewardFeed[i]?.agent || '').toUpperCase();
      if (agent.includes('CODER') || agent.includes('ENGINEER')) {
        return rewardFeed[i].id;
      }
    }
    return null;
  }, [rewardFeed]);

  useEffect(() => {
    if (!coderSignal) return undefined;
    setActiveStepIdx(0);
    let step = 0;
    const timer = setInterval(() => {
      step += 1;
      if (step > 3) {
        clearInterval(timer);
        setActiveStepIdx(-1);
        return;
      }
      setActiveStepIdx(step);
    }, 280);
    return () => clearInterval(timer);
  }, [coderSignal]);

  const validator = lastValidatorResult || chosenRun || {};
  const checksApplied = Array.isArray(validator.checks_applied) ? validator.checks_applied : [];
  const validatorPass = parseStatus(validator.status) === 'pass';
  const hasVerdict = Boolean(verdict);

  const extracted = Boolean(apkPackage) || Number(fileSizeBytes) > 0;
  const permCount = Number(apkPermissionCount) || 0;
  const fileCount = Number(apkFileCount) || 0;
  // telemetry.network carries the count of URLs + IPs harvested from the DEX.
  const netCount = Number(telemetry.network) || 0;
  const sizeKb = (Number(fileSizeBytes) || 0) / 1024;

  const checks = [
    {
      id: 'extract',
      label: 'APK Extraction (Androguard)',
      state: extracted ? 'pass' : 'pending',
      detail: extracted ? `${fileCount} files · ${sizeKb.toFixed(1)} KB` : 'Awaiting APK stream',
    },
    {
      id: 'manifest',
      label: 'Manifest & Permission Audit',
      state: extracted ? 'pass' : 'pending',
      detail: permCount > 0 ? `${permCount} permission(s) parsed` : 'Parsing AndroidManifest.xml',
    },
    {
      id: 'components',
      label: 'Exported Component Scan',
      state: checksApplied.includes('Exported-component scan') ? 'pass' : (extracted ? 'pass' : 'pending'),
      detail: checksApplied.includes('Exported-component scan') ? 'Attack surface enumerated' : 'Scanning components',
    },
    {
      id: 'threat',
      label: 'Threat Scoring',
      state: hasVerdict ? 'pass' : 'pending',
      detail: hasVerdict
        ? `${verdict.threat_score}/100 · ${String(verdict.threat_level || '').replace(/^THREAT_/, '')}`
        : 'Awaiting agent verdict',
    },
    {
      id: 'c2',
      label: 'Network / C2 Indicators',
      state: hasVerdict ? 'pass' : 'pending',
      detail: netCount > 0
        ? `${netCount} network indicator(s)`
        : (hasVerdict ? 'No hardcoded endpoints' : 'Harvesting DEX strings'),
    },
  ];

  const failed = checks.some((c) => c.state === 'fail');
  const passed = hasVerdict && validatorPass;
  const gateLabel = failed ? 'BLOCKED' : passed ? 'REPORT READY' : (isRunning ? 'ANALYZING' : 'PENDING');
  const gateClass = failed ? 'text-red-300 border-red-500/40 bg-red-500/10' : passed ? 'text-sky-200 border-sky-400/40 bg-sky-400/10' : 'text-zinc-400 border-white/10 bg-white/[0.03]';

  return (
    <div className="glass-surface p-3 h-full min-h-0 flex flex-col">
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-white/10">
        <span className="prism-title text-[10px] font-bold uppercase tracking-widest">
          Forensic Pipeline Checks
        </span>
        <span className={`text-[10px] px-2.5 py-1 border rounded-full font-mono font-bold shadow-[0_0_20px_rgba(96,165,250,0.18)] ${gateClass}`}>
          {gateLabel}
        </span>
      </div>

      <div className="flex-1 min-h-0 space-y-1.5 overflow-y-auto overflow-x-hidden pr-1 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent">
        {checks.map((check, idx) => {
          const isFocused = activeStepIdx === idx;
          const styles = getRowStyles(check.state, isFocused);
          return (
            <motion.div
              key={check.id}
              animate={isFocused ? { scale: [1, 1.01, 1], opacity: [0.85, 1, 0.9] } : { scale: 1, opacity: 1 }}
              transition={{ duration: 0.45, repeat: isFocused ? Infinity : 0 }}
              className={`glass-inset rounded-xl border ${styles.border} ${styles.bg} px-2.5 py-2`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className={`min-w-0 text-[10px] font-semibold leading-snug break-words ${styles.text}`}>{check.label}</span>
                <span className={`text-[11px] font-mono ${styles.markClass}`}>{styles.mark}</span>
              </div>
              <div className="text-[9px] text-zinc-500 font-mono mt-1 break-words">{check.detail}</div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
