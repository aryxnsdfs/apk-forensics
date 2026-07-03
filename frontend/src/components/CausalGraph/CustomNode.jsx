import { Handle, Position } from 'reactflow';

const TYPE_STYLES = {
  error:      { symbol: 'ERR', bg: 'rgba(239,68,68,0.14)', border: '#f87171' },
  fix:        { symbol: 'FIX', bg: 'rgba(96,165,250,0.14)', border: '#93c5fd' },
  escalation: { symbol: 'ESC', bg: 'rgba(245,158,11,0.13)', border: '#fbbf24' },
  resolution: { symbol: 'RES', bg: 'rgba(59,130,246,0.16)', border: '#60a5fa' },
  fork:       { symbol: 'FRK', bg: 'rgba(168,85,247,0.16)', border: '#a78bfa' },
};

export default function CustomNode({ data }) {
  const { label, nodeType, detail, color } = data;
  const style = TYPE_STYLES[nodeType] || { symbol: '---', bg: '#71717a20', border: '#71717a' };

  return (
    <div
      className="px-3 py-2.5 rounded-2xl border w-[240px] backdrop-blur-xl"
      style={{
        background: `linear-gradient(145deg, rgba(255,255,255,0.1), rgba(255,255,255,0.025)), rgba(8,10,18,0.72)`,
        borderColor: `${color || style.border}66`,
        boxShadow: `0 18px 45px rgba(0,0,0,0.28), 0 0 22px ${(color || style.border)}20, inset 0 1px 0 rgba(255,255,255,0.08)`,
      }}
    >
      <Handle type="target" position={Position.Top} className="!bg-blue-300 !w-2.5 !h-2.5 !border !border-white/30" />
      <div className="flex items-start gap-1.5">
        <span
          className="shrink-0 forensic-token text-[8px] font-bold px-1.5 py-0.5 rounded-full mt-0.5"
          style={{ backgroundColor: style.bg, color: style.border, border: `1px solid ${style.border}40` }}
        >
          {style.symbol}
        </span>
        <span className="flex-1 min-w-0 text-[11px] font-semibold text-zinc-200 leading-snug break-words">
          {label}
        </span>
        {data.points !== undefined && (
          <span className={`shrink-0 mt-0.5 forensic-token text-[9px] font-bold ${data.points > 0 ? 'text-blue-200' : 'text-red-300'}`}>
            {data.points > 0 ? '+' : ''}{data.points.toFixed(2)}
          </span>
        )}
      </div>
      {detail && (
        <p className="text-[9px] forensic-token leading-snug mt-1.5 break-words" style={{ color: (color || '#a1a1aa') + 'cc' }}>
          {detail.replace(/\*\*/g, '').replace(/\*/g, '')}
        </p>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-violet-300 !w-2.5 !h-2.5 !border !border-white/30" />
    </div>
  );
}
