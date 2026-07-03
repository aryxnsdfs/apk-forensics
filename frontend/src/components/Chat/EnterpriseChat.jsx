import { useRef, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSimulationDispatch, useSimulationState } from '../../store/simulationStore';
import { ShieldAlert, Bot, Terminal, Briefcase, Users, Gauge } from 'lucide-react';

const THREAT_TXT = { LOW: 'text-emerald-400', MEDIUM: 'text-amber-400', HIGH: 'text-red-400', CRITICAL: 'text-red-300' };
const TOKEN_COLORS = {
  THREAT_LOW: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  THREAT_MEDIUM: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  THREAT_HIGH: 'border-red-500/35 bg-red-500/10 text-red-300',
  THREAT_CRITICAL: 'border-red-400/40 bg-red-500/15 text-red-200',
};

function cleanText(value) {
  return String(value || '').replace(/\*\*/g, '').replace(/\*/g, '').trim();
}

function tokenClass(token) {
  if (TOKEN_COLORS[token]) return TOKEN_COLORS[token];
  if (/^FLAG_/i.test(token)) return 'border-red-500/25 bg-red-500/10 text-red-300';
  if (/^(INTERNET|READ_SMS|RECEIVE_SMS|SEND_SMS|ACCESS_|CAMERA|CONTACTS)/i.test(token)) return 'border-sky-500/25 bg-sky-500/10 text-sky-300';
  if (/^ETA_/i.test(token)) return 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300';
  return 'border-zinc-700 bg-zinc-900/70 text-zinc-300';
}

function extractJsonBlock(text) {
  const jsonStart = text.indexOf('{');
  const jsonEnd = text.lastIndexOf('}');
  if (jsonStart === -1 || jsonEnd <= jsonStart) return { before: text, json: null };

  const jsonText = text.slice(jsonStart, jsonEnd + 1);
  try {
    return {
      before: text.slice(0, jsonStart).replace(/\bJSON:\s*$/i, '').trim(),
      after: text.slice(jsonEnd + 1).trim(),
      json: JSON.parse(jsonText),
    };
  } catch {
    return { before: text, json: null };
  }
}

function parseSections(text) {
  const sections = [];
  const sectionPattern = /\b(EVIDENCE|ANSWER|RCA|MITIGATION):\s*/gi;
  const matches = [...text.matchAll(sectionPattern)];
  if (matches.length === 0) return { lead: text.trim(), sections };

  const lead = text.slice(0, matches[0].index).trim();
  matches.forEach((match, index) => {
    const start = match.index + match[0].length;
    const end = index + 1 < matches.length ? matches[index + 1].index : text.length;
    const body = text.slice(start, end).trim();
    sections.push({ label: match[1].toUpperCase(), body });
  });
  return { lead, sections };
}

function splitProtocol(lead) {
  const parts = lead.split('|').map((part) => part.trim()).filter(Boolean);
  if (parts.length < 2) return { title: lead, chips: [] };
  return { title: parts[0], chips: parts.slice(1) };
}

function listFromValue(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  return String(value).split(/\n|;\s*/).map((item) => item.replace(/^-\s*/, '').trim()).filter(Boolean);
}

const LEVEL_PILL = {
  BENIGN:   'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  LOW:      'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  MEDIUM:   'bg-amber-500/15 text-amber-300 border-amber-500/30',
  HIGH:     'bg-red-500/15 text-red-300 border-red-500/40',
  CRITICAL: 'bg-red-500/20 text-red-200 border-red-500/50',
};

function StructuredJson({ data }) {
  const indicatorList = data.indicators || data.evidence || [];
  const flags = indicatorList
    .map((it) => (typeof it === 'string' ? it : it.flag))
    .filter(Boolean);
  const mitigations = listFromValue(data.mitigation);
  const level = String(data.threat_level || '').replace(/THREAT_/i, '').toUpperCase();
  const pill = LEVEL_PILL[level] || 'bg-zinc-700/30 text-zinc-300 border-zinc-600';

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="mt-2 rounded-xl border border-zinc-800 bg-zinc-950/50 overflow-hidden transition-shadow duration-300 hover:shadow-lg hover:shadow-black/40"
    >
      {/* Verdict header */}
      <div className="flex items-center gap-2.5 px-3.5 py-3 border-b border-zinc-800/70 bg-gradient-to-r from-zinc-900/60 to-transparent">
        {level && (
          <span className={`font-display text-[11px] font-bold px-2.5 py-1 rounded-md border ${pill}`}>{level}</span>
        )}
        {data.threat_score !== undefined && (
          <span className="font-mono text-[12px] text-zinc-400 tabular-nums">
            <span className="text-zinc-100 font-bold">{data.threat_score}</span>
            <span className="text-zinc-600">/100</span>
          </span>
        )}
        {data.malware_family && (
          <span className="ml-auto text-[12px] text-zinc-300">
            <span className="text-zinc-600 text-[10px] uppercase tracking-wide">family </span>
            <span className="font-display font-medium">{data.malware_family}</span>
          </span>
        )}
      </div>

      {/* Indicators as inline chips */}
      {flags.length > 0 && (
        <div className="px-3.5 py-3 border-b border-zinc-800/70">
          <span className="block text-[9px] text-zinc-500 uppercase tracking-widest mb-2">Indicators</span>
          <div className="flex flex-wrap gap-1.5">
            {flags.slice(0, 8).map((f, i) => (
              <motion.span
                key={`${f}-${i}`}
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.05 * i, duration: 0.2 }}
                className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-red-500/25 bg-red-500/10 text-red-300 transition-colors hover:bg-red-500/20"
              >
                {f}
              </motion.span>
            ))}
          </div>
        </div>
      )}

      {data.rca && (
        <div className="px-3 py-2.5 border-b border-zinc-800/70">
          <span className="block text-[9px] text-zinc-500 uppercase tracking-widest mb-1">Root Cause</span>
          <p className="text-[11px] leading-relaxed text-zinc-300 break-words">{data.rca}</p>
        </div>
      )}

      {Array.isArray(data.impact) && data.impact.length > 0 && (
        <div className="px-3 py-2.5 border-b border-zinc-800/70">
          <span className="block text-[9px] text-zinc-500 uppercase tracking-widest mb-1.5">Potential Impact</span>
          <ul className="flex flex-col gap-1">
            {data.impact.slice(0, 5).map((item, index) => (
              <li key={index} className="flex items-start gap-2 text-[11px] leading-relaxed text-zinc-300 break-words">
                <span className="shrink-0 text-red-400/70 mt-px">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {mitigations.length > 0 && (
        <div className="px-3 py-2.5">
          <span className="block text-[9px] text-zinc-500 uppercase tracking-widest mb-1.5">Mitigation</span>
          <div className="flex flex-col gap-1.5">
            {mitigations.slice(0, 5).map((item, index) => (
              <div key={index} className="flex items-start gap-2">
                <span className="shrink-0 w-4 h-4 rounded-full bg-zinc-800 text-zinc-400 text-[9px] font-mono flex items-center justify-center mt-px">{index + 1}</span>
                <span className="text-[11px] leading-relaxed text-zinc-300 break-words">{item}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}

function SectionBody({ section }) {
  const items = listFromValue(section.body);
  const isList = section.label === 'EVIDENCE' || items.length > 1;

  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-950/35 px-2 py-1.5">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">{section.label}</span>
      {isList ? (
        <div className="mt-1 space-y-1">
          {items.map((item, index) => (
            <p key={index} className="text-[11px] leading-snug text-zinc-300 break-words">{item}</p>
          ))}
        </div>
      ) : (
        <p className="mt-1 text-[11px] leading-snug text-zinc-300 break-words">{section.body}</p>
      )}
    </div>
  );
}

// A genuine machine-to-machine line looks like "TAG | FIELD | FIELD" with an
// all-caps leading token and short parts. Prose ("Parsed the manifest...") must
// NOT be treated as a protocol line, or it renders as a shouty uppercase chip.
function isProtocolLine(lead) {
  if (!lead || !lead.includes('|')) return false;
  const parts = lead.split('|').map((s) => s.trim()).filter(Boolean);
  if (parts.length < 2) return false;
  return /^[A-Z0-9_]{2,24}$/.test(parts[0]) && parts.every((p) => p.length <= 40);
}

function MessageBody({ msg }) {
  const raw = cleanText(msg.english || msg.m2m || msg.think || '');
  const { before, json } = extractJsonBlock(raw);

  // Structured verdict → clean card (optionally with a lead sentence).
  if (json) {
    const leadTxt = (before || '').trim();
    return (
      <div className="space-y-2 min-w-0">
        {leadTxt && (
          <p className="text-[13px] text-zinc-200 leading-relaxed whitespace-pre-wrap break-words">{leadTxt}</p>
        )}
        <StructuredJson data={json} />
      </div>
    );
  }

  const { lead, sections } = parseSections(before);

  // Genuine M2M protocol line → title + chips.
  if (isProtocolLine(lead)) {
    const { title, chips } = splitProtocol(lead);
    return (
      <div className="space-y-2 min-w-0">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-zinc-100">
            {title}
          </span>
          {chips.slice(0, 12).map((chip, index) => (
            <span key={`${chip}-${index}`} className={`rounded border px-1.5 py-0.5 text-[10px] font-mono ${tokenClass(chip)}`}>
              {chip}
            </span>
          ))}
        </div>
        {sections.length > 0 && (
          <div className="space-y-1.5">
            {sections.map((section) => <SectionBody key={section.label} section={section} />)}
          </div>
        )}
      </div>
    );
  }

  // Plain prose (the common case for agent reasoning).
  return (
    <div className="space-y-2 min-w-0">
      {lead && (
        <p className="text-[13px] text-zinc-200 leading-relaxed whitespace-pre-wrap break-words">{lead}</p>
      )}
      {sections.length > 0 && (
        <div className="space-y-1.5">
          {sections.map((section) => <SectionBody key={section.label} section={section} />)}
        </div>
      )}
    </div>
  );
}

// Parse the Chief Security Officer verdict line: "VERDICT | THREAT_X | Family | FLAG_A FLAG_B | ETA"
function deriveVerdict(messages) {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const raw = String(messages[i]?.m2m || '').trim();
    if (/^VERDICT/i.test(raw)) {
      const parts = raw.split('|').map((s) => s.trim());
      const level = (parts[1] || '').replace(/THREAT[_\s-]?/i, '').toUpperCase();
      const family = parts[2] || '';
      const flags = (parts[3] || '').split(/\s+/).filter((f) => /^FLAG/i.test(f));
      return { level, family, flags };
    }
  }
  return null;
}

export default function EnterpriseChat() {
  const dispatch = useSimulationDispatch();
  const { messages, disagreement, scenarioContext, taskViews, queuedTaskIds, selectedTaskView, scenarioComplete, spent, budget, rewardFeed, totalReward } = useSimulationState();
  const scrollRef = useRef(null);
  const [expandedThink, setExpandedThink] = useState({});
  const verdict = deriveVerdict(messages);

  const activeTask = scenarioContext?.task_id;
  const availableTasks = new Set([
    ...Object.keys(taskViews || {}),
    ...(activeTask ? [activeTask] : []),
  ]);
  
  // Show task switcher if we have multiple tasks queued (sequence) or already started
  const showTaskSwitcher = (queuedTaskIds && queuedTaskIds.length > 1) || availableTasks.size > 1;
  const taskButtons = [
    { key: 'task_easy_gpu_oom', label: 'EASY' },
    { key: 'task_medium_schema_drift', label: 'MED' },
    { key: 'task_hard_canary_regression', label: 'HARD' },
  ];

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const toggleThink = (id) => {
    setExpandedThink((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  // Map agent id to Lucide icon component
  const getAgentIcon = (agentId, color) => {
    const iconProps = { size: 16, color };
    switch (agentId) {
      case 'commander': return <ShieldAlert {...iconProps} />;
      case 'detective': return <Bot {...iconProps} />;
      case 'coder': return <Terminal {...iconProps} />;
      case 'manager': return <Users {...iconProps} />;
      case 'evaluator': return <Gauge {...iconProps} />;
      case 'db_admin': return <Briefcase {...iconProps} />;
      case 'dba_agent': return <Briefcase {...iconProps} />;
      case 'sre_agent': return <Gauge {...iconProps} />;
      case 'security_agent': return <ShieldAlert {...iconProps} />;
      case 'compliance_agent': return <ShieldAlert {...iconProps} />;
      default: return (
        <span className="text-[8px] font-bold font-mono tracking-tight" style={{ color }}>
          {agentId?.substring(0, 3).toUpperCase() || '?'}
        </span>
      );
    }
  };

  return (
    <div className="flex flex-col h-full panel-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <svg className="w-3.5 h-3.5 text-zinc-400" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M2 4h12v8a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V4z" />
            <path d="M2 4l6 4 6-4" />
          </svg>
          <span className="text-xs font-semibold text-zinc-300">AI Chat</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500 font-mono">
            {messages.length} msgs
          </span>
        </div>
        <div className="flex items-center gap-2">
          {showTaskSwitcher && (
            <div className="flex items-center gap-1 rounded-md border border-zinc-800 bg-zinc-900/70 p-1">
              {taskButtons.map((button) => {
                const isSelected = selectedTaskView === button.key;
                const isEnabled = availableTasks.has(button.key);
                return (
                  <button
                    key={button.key}
                    type="button"
                    disabled={!isEnabled}
                    onClick={() => isEnabled && dispatch({ type: 'SELECT_TASK_VIEW', payload: button.key })}
                    className={`px-2 py-1 rounded text-[10px] font-mono transition-colors ${
                      isSelected
                        ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-500/30'
                        : isEnabled
                        ? 'bg-zinc-800 text-zinc-300 border border-zinc-700 hover:bg-zinc-700'
                        : 'text-zinc-600 cursor-not-allowed'
                    }`}
                  >
                    {button.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Disagreement Banner */}
      <AnimatePresence>
        {disagreement.active && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="bg-amber-900/20 border-b border-amber-800/50 px-3 py-2 overflow-hidden"
          >
            <div className="flex items-center gap-2 mb-1">
              <svg className="w-3.5 h-3.5 text-amber-400" viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 1l7 14H1L8 1zm0 4v4m0 2v1" stroke="#18181b" strokeWidth="1.2" fill="none" />
                <path d="M8 1l7 14H1L8 1z" fillOpacity="0.2" />
              </svg>
              <span className="text-amber-400 text-xs font-bold">REASONING FORK</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <div className="bg-zinc-900/80 rounded p-2 border border-amber-800/30">
                <span className="text-blue-400 font-mono">{disagreement.position1?.agent}</span>
                <p className="text-zinc-400 mt-0.5">{disagreement.position1?.action}</p>
                <p className="text-red-400 font-mono mt-0.5">{disagreement.position1?.cost}</p>
              </div>
              <div className="bg-zinc-900/80 rounded p-2 border border-amber-800/30">
                <span className="text-amber-400 font-mono">{disagreement.position2?.agent}</span>
                <p className="text-zinc-400 mt-0.5">{disagreement.position2?.action}</p>
                <p className="text-emerald-400 font-mono mt-0.5">{disagreement.position2?.cost}</p>
              </div>
            </div>
            {disagreement.resolution && (
              <p className="text-emerald-400 text-[10px] mt-1 font-mono">
                <span className="text-emerald-500 mr-1">[RESOLVED]</span>
                {disagreement.resolution}
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3.5">
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className="group"
            >
              <div className="flex items-start gap-3">
                {/* Agent Avatar — gradient tile with ring */}
                <div
                  className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 mt-0.5 shadow-lg"
                  style={{
                    background: `linear-gradient(135deg, ${(msg.agent.color || '#71717a')}33, ${(msg.agent.color || '#71717a')}0d)`,
                    border: `1px solid ${msg.agent.color || '#71717a'}55`,
                    boxShadow: `0 0 12px ${msg.agent.color || '#71717a'}18`,
                  }}
                >
                  {getAgentIcon(msg.agent.id, msg.agent.color || '#71717a')}
                </div>

                <div className="flex-1 min-w-0">
                  {/* Agent Name + Timestamp */}
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="font-display text-[13.5px] font-semibold tracking-tight" style={{ color: msg.agent.color || '#71717a' }}>
                      {msg.agent.name || msg.agent.id || 'Agent'}
                    </span>
                    <span className="text-[9px] text-zinc-600 font-mono tabular-nums">{msg.timestamp}</span>
                    {msg.points !== undefined && msg.points !== 0 && (
                      <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${msg.points > 0 ? 'bg-emerald-900/30 text-emerald-400' : 'bg-red-900/30 text-red-500'}`}>
                        {msg.points > 0 ? '+' : ''}{msg.points.toFixed(2)} pts
                      </span>
                    )}
                    {msg.think && (
                      <button
                        onClick={() => toggleThink(msg.id)}
                        className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-700 transition-colors font-mono"
                      >
                        {expandedThink[msg.id] ? 'HIDE REASONING' : 'REASONING'}
                      </button>
                    )}
                  </div>

                  {/* Message Content — human-readable only */}
                  <div
                    className="rounded-xl border border-zinc-800/70 border-l-[3px] px-3.5 py-3 transition-all duration-200 group-hover:border-zinc-700/80"
                    style={{
                      borderLeftColor: (msg.agent.color || '#71717a') + 'cc',
                      background: 'linear-gradient(180deg, rgba(39,39,42,0.35), rgba(24,24,27,0.25))',
                    }}
                  >
                    <MessageBody msg={msg} />
                  </div>

                  {/* Hidden CoT Block */}
                  <AnimatePresence>
                    {msg.think && expandedThink[msg.id] && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <div className="mt-1.5 p-2 rounded bg-purple-900/10 border border-purple-800/20">
                          <span className="text-[9px] text-purple-400 font-mono block mb-1">{'<think>'}</span>
                          <p className="text-[10px] text-zinc-400 leading-relaxed italic">{(msg.think || '').replace(/\*\*/g, '').replace(/\*/g, '')}</p>
                          <span className="text-[9px] text-purple-400 font-mono block mt-1">{'</think>'}</span>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {scenarioComplete && messages.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 }}
            className="mt-3 rounded-lg border border-emerald-500/30 bg-gradient-to-b from-emerald-950/40 to-zinc-900/80 overflow-hidden"
          >
            <div className="px-4 py-2 bg-emerald-500/10 border-b border-emerald-500/20 flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400" />
              <span className="text-[11px] font-bold text-emerald-300 uppercase tracking-widest">Incident Summary</span>
              <span className="ml-auto text-[9px] font-mono text-emerald-500/70">
                {scenarioContext?.source === 'inference_cli' ? 'inference.py complete' : 'Orchestration complete'}
              </span>
            </div>
            <div className="px-4 py-3">
              <table className="w-full text-[10px]">
                <tbody>
                  <tr className="border-b border-zinc-800/50">
                    <td className="py-1.5 text-zinc-500 font-medium w-28">Status</td>
                    <td className="py-1.5"><span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold text-[9px]">RESOLVED</span></td>
                  </tr>
                  {verdict && (
                    <tr className="border-b border-zinc-800/50">
                      <td className="py-1.5 text-zinc-500 font-medium">Threat Level</td>
                      <td className="py-1.5"><span className={`font-bold font-mono ${THREAT_TXT[verdict.level] || 'text-zinc-300'}`}>{verdict.level || '—'}</span></td>
                    </tr>
                  )}
                  {verdict?.family && (
                    <tr className="border-b border-zinc-800/50">
                      <td className="py-1.5 text-zinc-500 font-medium">Malware Family</td>
                      <td className="py-1.5 text-zinc-200 font-mono">{verdict.family}</td>
                    </tr>
                  )}
                  {verdict?.flags?.length > 0 && (
                    <tr className="border-b border-zinc-800/50">
                      <td className="py-1.5 text-zinc-500 font-medium align-top">Indicators Found</td>
                      <td className="py-1.5">
                        <div className="flex flex-wrap gap-1">
                          {verdict.flags.map((f, i) => (
                            <span key={i} className="px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 font-mono text-[9px]">{f}</span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                  <tr className="border-b border-zinc-800/50">
                    <td className="py-1.5 text-zinc-500 font-medium">Steps Taken</td>
                    <td className="py-1.5 text-zinc-300 font-mono">{messages.length}</td>
                  </tr>
                  <tr className="border-b border-zinc-800/50">
                    <td className="py-1.5 text-zinc-500 font-medium">Final Score</td>
                    <td className="py-1.5 text-emerald-400 font-bold font-mono">{totalReward.toFixed(3)}</td>
                  </tr>
                  <tr className="border-b border-zinc-800/50">
                    <td className="py-1.5 text-zinc-500 font-medium">AI Cost</td>
                    <td className="py-1.5 text-zinc-300 font-mono">${spent.toFixed(4)}</td>
                  </tr>
                  <tr className="border-b border-zinc-800/50">
                    <td className="py-1.5 text-zinc-500 font-medium">Budget Left</td>
                    <td className="py-1.5 text-zinc-300 font-mono">${(budget - spent).toFixed(3)}</td>
                  </tr>
                  <tr>
                    <td className="py-1.5 text-zinc-500 font-medium align-top">Rewards</td>
                    <td className="py-1.5 font-mono text-[9px] leading-relaxed">
                      <div className="flex flex-wrap gap-1">
                        {rewardFeed.length > 0 ? rewardFeed.map((r, i) => (
                          <span key={i} className={`px-1 py-0.5 rounded ${r.value >= 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}`}>
                            {r.value >= 0 ? '+' : ''}{r.value.toFixed(2)}
                          </span>
                        )) : <span className="text-zinc-600">—</span>}
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </motion.div>
        )}

        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-zinc-600">
            <svg className="w-8 h-8 text-zinc-700 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            <p className="text-xs">Awaiting scenario start...</p>
          </div>
        )}
      </div>

    </div>
  );
}
