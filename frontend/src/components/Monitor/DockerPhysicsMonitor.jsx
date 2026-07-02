import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { useSimulationState } from '../../store/simulationStore';

const GAUGES = [
  { key: 'ram',  label: 'RAM',  unit: 'MB', max: 900, thresholds: { warn: 700, crit: 860 } },
  { key: 'vram', label: 'VRAM', unit: 'MB', max: 500, thresholds: { warn: 380, crit: 480 } },
  { key: 'cpu',  label: 'CPU',  unit: '%',  max: 100, thresholds: { warn: 50,  crit: 80  } },
];

function getGaugeColor(value, thresholds) {
  if (value >= thresholds.crit) return { bar: 'bg-red-500',    text: 'text-red-400'     };
  if (value >= thresholds.warn) return { bar: 'bg-amber-500',  text: 'text-amber-400'   };
  return                               { bar: 'bg-emerald-500', text: 'text-emerald-400' };
}

const STATUS_MAP = {
  idle:     { label: 'IDLE',     color: 'bg-zinc-500',    pulse: false },
  running:  { label: 'RUNNING',  color: 'bg-emerald-500', pulse: true  },
  warning:  { label: 'WARNING',  color: 'bg-amber-500',   pulse: true  },
  critical: { label: 'CRITICAL', color: 'bg-red-500',     pulse: true  },
  stable:   { label: 'STABLE',   color: 'bg-emerald-500', pulse: false },
};

// Tag → colour mapping for structured think lines
const TAG_COLOURS = {
  '[STATE]':      'text-sky-400',
  '[METRICS]':    'text-violet-400',
  '[CONSTRAINT]': 'text-amber-400',
  '[ANALYSIS]':   'text-zinc-300',
  '[DECISION]':   'text-emerald-400',
};

function extractTraceJson(text) {
  const raw = String(text || '').replace(/\*\*/g, '').replace(/\*/g, '').trim();
  const start = raw.indexOf('{');
  const end = raw.lastIndexOf('}');
  if (start === -1 || end <= start) return { before: raw, after: '', json: null };

  try {
    return {
      before: raw.slice(0, start).replace(/\bJSON:\s*$/i, '').trim(),
      after: raw.slice(end + 1).trim(),
      json: JSON.parse(raw.slice(start, end + 1)),
    };
  } catch {
    return { before: raw, after: '', json: null };
  }
}

function traceTokenClass(token) {
  if (/^THREAT_(HIGH|CRITICAL)/i.test(token)) return 'border-red-500/30 bg-red-500/10 text-red-300';
  if (/^THREAT_MEDIUM/i.test(token)) return 'border-amber-500/30 bg-amber-500/10 text-amber-300';
  if (/^FLAG_/i.test(token)) return 'border-red-500/20 bg-red-500/10 text-red-300';
  if (/SMS|INTERNET|READ_|RECEIVE_/i.test(token)) return 'border-sky-500/20 bg-sky-500/10 text-sky-300';
  return 'border-zinc-800 bg-zinc-950 text-zinc-400';
}

function TraceProtocol({ text }) {
  const parts = String(text || '').split('|').map((part) => part.trim()).filter(Boolean);
  if (parts.length < 2) return null;

  return (
    <div className="flex flex-wrap gap-1">
      <span className="rounded border border-zinc-700 bg-zinc-950 px-1.5 py-0.5 text-[8px] font-bold text-zinc-200">
        {parts[0]}
      </span>
      {parts.slice(1, 8).map((part, index) => (
        <span key={`${part}-${index}`} className={`rounded border px-1 py-0.5 text-[8px] ${traceTokenClass(part)}`}>
          {part}
        </span>
      ))}
    </div>
  );
}

function TraceJsonSummary({ data }) {
  const indicators = data.indicators || data.evidence || [];
  const mitigations = Array.isArray(data.mitigation) ? data.mitigation : [];

  return (
    <div className="mt-1.5 rounded border border-zinc-800 bg-zinc-950/70 overflow-hidden">
      <div className="grid grid-cols-2 gap-px bg-zinc-800/60">
        {data.threat_level && (
          <div className="bg-[#0d0d0d] px-1.5 py-1">
            <span className="block text-[8px] text-zinc-600 uppercase">Threat</span>
            <span className="text-[9px] font-bold text-amber-300">{String(data.threat_level).replace('THREAT_', '')}</span>
          </div>
        )}
        {data.threat_score !== undefined && (
          <div className="bg-[#0d0d0d] px-1.5 py-1">
            <span className="block text-[8px] text-zinc-600 uppercase">Score</span>
            <span className="text-[9px] font-bold text-emerald-300">{data.threat_score}</span>
          </div>
        )}
      </div>
      {indicators.slice(0, 3).map((item, index) => (
        <div key={index} className="border-t border-zinc-800 px-1.5 py-1">
          <span className="text-[8px] font-bold text-red-300">{typeof item === 'string' ? item : item.flag || `FINDING_${index + 1}`}</span>
          {typeof item !== 'string' && (
            <p className="text-[9px] leading-snug text-zinc-400 break-words">{item.detail || item.where || String(item)}</p>
          )}
        </div>
      ))}
      {data.rca && (
        <div className="border-t border-zinc-800 px-1.5 py-1">
          <span className="text-[8px] font-bold text-zinc-500">RCA</span>
          <p className="text-[9px] leading-snug text-zinc-400 break-words">{data.rca}</p>
        </div>
      )}
      {mitigations.length > 0 && (
        <div className="border-t border-zinc-800 px-1.5 py-1">
          <span className="text-[8px] font-bold text-zinc-500">MITIGATION</span>
          {mitigations.slice(0, 3).map((item, index) => (
            <p key={index} className="text-[9px] leading-snug text-zinc-400 break-words">{index + 1}. {item}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function TraceEntryBody({ text }) {
  const { before, after, json } = extractTraceJson(text);
  if (json) {
    const afterTokens = after.split(/\s+/).filter((token) => /^(FLAG_|THREAT_|INTERNET|READ_|RECEIVE_|SMS)/i.test(token));
    return (
      <div className="space-y-1">
        <TraceProtocol text={before} />
        <TraceJsonSummary data={json} />
        {afterTokens.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {afterTokens.slice(0, 8).map((token, index) => (
              <span key={`${token}-${index}`} className={`rounded border px-1 py-0.5 text-[8px] ${traceTokenClass(token)}`}>
                {token}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  return text.split('\n').map((line, i) => (
    <ThinkLine key={i} line={line} />
  ));
}

/** Render a single line of a think block with tag colouring */
function ThinkLine({ line }) {
  const trimmed = line.trimStart();
  const matchedTag = Object.keys(TAG_COLOURS).find(t => trimmed.startsWith(t));
  if (matchedTag) {
    const rest = trimmed.slice(matchedTag.length);
    return (
      <div className="flex gap-1.5 leading-relaxed">
        <span className={`shrink-0 font-bold text-[9px] ${TAG_COLOURS[matchedTag]}`}>{matchedTag}</span>
        <span className="text-[9px] text-zinc-400 break-words min-w-0">{rest}</span>
      </div>
    );
  }
  // Indented continuation lines (options / sub-points)
  return (
    <div className="pl-[68px] text-[9px] text-zinc-500 leading-relaxed break-words">
      {trimmed || '\u00a0'}
    </div>
  );
}

export default function DockerPhysicsMonitor() {
  const {
    telemetry, preflight, validatorRuntime, lastValidatorResult, reasoningTrace,
    verdict, apkFileCount, apkPermissionCount, fileSizeBytes,
  } = useSimulationState();
  const traceScrollRef = useRef(null);

  const isCritical = telemetry.containerStatus === 'critical';
  const runtime = validatorRuntime || telemetry.validator_runtime || {};

  const validatorStatus = lastValidatorResult?.status || telemetry.last_validator_status || 'scanning';
  const isPass          = validatorStatus === 'PASS' || validatorStatus === 'pass';
  const validatorLabel  = lastValidatorResult?.validation_label || runtime.label || 'Androguard Static Parser';
  const validatorMode   = lastValidatorResult?.validation_mode  || runtime.mode  || 'Local Air-Gapped';
  const validatorDetail = lastValidatorResult?.validator_detail || telemetry.validator_detail || runtime.detail
                          || 'Package signatures verified locally.';

  // ── Real APK forensic metrics (from the live pipeline) ──
  const sizeBytes = Number(fileSizeBytes) || 0;
  const sizeLabel = sizeBytes <= 0 ? '—'
    : sizeBytes < 1024 * 1024 ? `${(sizeBytes / 1024).toFixed(1)} KB`
    : `${(sizeBytes / (1024 * 1024)).toFixed(2)} MB`;
  const fileCount = Number(apkFileCount) || 0;
  const permCount = Number(apkPermissionCount) || 0;
  const netCount = Number(telemetry.network) || 0;
  const threatScore = verdict?.threat_score ?? null;
  const threatLevel = verdict?.threat_level || null;
  const threatBar =
    threatLevel === 'THREAT_HIGH' ? { bar: 'bg-red-500', text: 'text-red-400' }
    : threatLevel === 'THREAT_MEDIUM' ? { bar: 'bg-amber-500', text: 'text-amber-400' }
    : { bar: 'bg-emerald-500', text: 'text-emerald-400' };

  const forensicMetrics = [
    { label: 'APK Size', value: sizeLabel },
    { label: 'Extracted Files', value: fileCount || '—' },
    { label: 'Permissions', value: permCount || '—' },
    { label: 'Network Indicators', value: netCount || 0 },
  ];

  // Auto-scroll the think-log to bottom (inner container only — never the sidebar)
  useEffect(() => {
    const el = traceScrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [reasoningTrace.length]);

  return (
    <div className={`flex flex-col gap-3 panel-card p-3 transition-all ${isCritical ? 'gauge-warning' : ''}`}>

      {/* ── APK Forensic Metrics ── */}
      <div className="space-y-2.5">
        <span className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
          APK Forensic Metrics
        </span>

        {/* Threat score gauge */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-zinc-500 font-mono">THREAT SCORE</span>
            <span className={`text-[10px] font-mono font-bold ${threatBar.text}`}>
              {threatScore === null ? '—' : `${threatScore}/100`}
              {threatLevel ? ` · ${threatLevel.replace('THREAT_', '')}` : ''}
            </span>
          </div>
          <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <motion.div
              className={`h-full ${threatBar.bar} rounded-full`}
              animate={{ width: `${Math.min(Number(threatScore) || 0, 100)}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
          </div>
        </div>

        {/* Metric rows */}
        <div className="grid grid-cols-2 gap-1.5 pt-0.5">
          {forensicMetrics.map((m) => (
            <div key={m.label} className="rounded border border-zinc-800 bg-zinc-950/60 px-2 py-1.5">
              <span className="block text-[8px] text-zinc-600 uppercase tracking-wide">{m.label}</span>
              <span className="text-[11px] font-mono font-bold text-zinc-200">{m.value}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="h-px bg-zinc-800" />

      {/* ── VRAM Reasoning Trace (think stream) ── */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
            Agent Thinking Matrix
          </span>
          <span className="text-[9px] font-mono text-zinc-600">
            {reasoningTrace.length > 0 ? `${reasoningTrace.length} steps` : 'awaiting run…'}
          </span>
        </div>

        {/* Terminal window */}
        <div className="rounded-md border border-zinc-800 bg-[#0d0d0d] overflow-hidden">
          {/* Chrome bar — no live badge, neutral */}
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-zinc-900/80 border-b border-zinc-800">
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
            <span className="ml-2 text-[9px] font-mono text-zinc-600">&lt;think&gt; stream</span>
          </div>

          {/* Scrollable think log */}
          <div ref={traceScrollRef} className="h-[210px] overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent p-2.5 space-y-3 font-mono">
            {reasoningTrace.length === 0 ? (
              <p className="text-[9px] text-zinc-700 italic pt-1">
                The model's forensic reasoning will appear here as it parses each APK component and assembles the attack-chain footprint…
              </p>
            ) : (
              reasoningTrace.map((entry) => (
                <div key={entry.id} className="space-y-0.5">
                  {/* Entry header: timestamp + agent */}
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[8px] text-zinc-700">{entry.ts}</span>
                    <span className="text-[8px] font-bold text-zinc-600 uppercase tracking-widest">
                      {entry.agent}
                    </span>
                  </div>
                  <TraceEntryBody text={entry.text} />
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="h-px bg-zinc-800" />

      {/* ── Validator Runtime ── */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">Analysis Engine</span>
          <ContainerStatusBadge status={telemetry.containerStatus} />
        </div>
        <div className="grid grid-cols-1 gap-1.5 text-[10px]">
          <InfoRow label="ENGINE" value={validatorLabel} />
          <InfoRow label="MODE"      value={validatorMode}  />
          <InfoRow
            label="STATUS"
            value={validatorStatus.toUpperCase()}
            valueClass={isPass ? 'text-emerald-400 font-bold' : 'text-zinc-400 font-bold'}
          />
          <InfoRow label="DETAIL" value={validatorDetail} valueClass="text-zinc-400" />
        </div>
      </div>

      <div className="h-px bg-zinc-800" />

      {/* ── Pre-Flight Check ── */}
      <div className="space-y-1.5">
        <span className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">Pre-Flight Check</span>
        <PreFlightItem label="Signature Match"  status={preflight.budget} />
        <PreFlightItem label="Permission Audit" status={preflight.spof}   />
        <PreFlightItem label="C2 Domain Check"   status={preflight.sla}    />
      </div>
    </div>
  );
}

function ContainerStatusBadge({ status }) {
  const info = STATUS_MAP[status] || STATUS_MAP.idle;
  return (
    <div className="flex items-center gap-1.5">
      <div className={`w-1.5 h-1.5 rounded-full ${info.color} ${info.pulse ? 'status-dot-live' : ''}`} />
      <span className="text-[9px] font-mono text-zinc-500">{info.label}</span>
    </div>
  );
}

function PreFlightItem({ label, status }) {
  const icon  = status === null ? '○' : status ? '✓' : '✗';
  const color = status === null ? 'text-zinc-600' : status ? 'text-emerald-400' : 'text-red-400';
  return (
    <div className="flex items-center gap-1.5">
      <span className={`text-xs font-mono ${color}`}>{icon}</span>
      <span className="text-[10px] text-zinc-500">{label}</span>
    </div>
  );
}

function InfoRow({ label, value, valueClass = 'text-zinc-200' }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1 border-b border-zinc-800/60 last:border-b-0">
      <span className="text-[9px] text-zinc-600 uppercase tracking-widest font-mono shrink-0">{label}</span>
      <span className={`text-[10px] font-mono text-right break-words ${valueClass}`}>{value}</span>
    </div>
  );
}
