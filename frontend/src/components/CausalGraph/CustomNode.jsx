import { Handle, Position } from 'reactflow';

const TYPE_STYLES = {
  error:      { symbol: 'ERR', bg: '#ef444420', border: '#ef4444' },
  fix:        { symbol: 'FIX', bg: '#10b98120', border: '#10b981' },
  escalation: { symbol: 'ESC', bg: '#f59e0b20', border: '#f59e0b' },
  resolution: { symbol: 'RES', bg: '#3b82f620', border: '#3b82f6' },
  fork:       { symbol: 'FRK', bg: '#a855f720', border: '#a855f7' },
};

export default function CustomNode({ data }) {
  const { label, nodeType, detail, color } = data;
  const style = TYPE_STYLES[nodeType] || { symbol: '---', bg: '#71717a20', border: '#71717a' };

  return (
    <div
      className="px-3 py-2.5 rounded-lg border w-[240px]"
      style={{
        backgroundColor: '#18181b',
        borderColor: color + '60',
        boxShadow: `0 0 8px ${color}15`,
      }}
    >
      <Handle type="target" position={Position.Top} className="!bg-zinc-600 !w-2 !h-2 !border-0" />
      <div className="flex items-start gap-1.5">
        <span
          className="shrink-0 text-[8px] font-bold font-mono px-1 py-0.5 rounded mt-0.5"
          style={{ backgroundColor: style.bg, color: style.border, border: `1px solid ${style.border}40` }}
        >
          {style.symbol}
        </span>
        <span className="flex-1 min-w-0 text-[11px] font-semibold text-zinc-200 leading-snug break-words">
          {label}
        </span>
        {data.points !== undefined && (
          <span className={`shrink-0 mt-0.5 font-mono text-[9px] font-bold ${data.points > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {data.points > 0 ? '+' : ''}{data.points.toFixed(2)}
          </span>
        )}
      </div>
      {detail && (
        <p className="text-[9px] font-mono leading-snug mt-1.5 break-words" style={{ color: (color || '#a1a1aa') + 'cc' }}>
          {detail.replace(/\*\*/g, '').replace(/\*/g, '')}
        </p>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-zinc-600 !w-2 !h-2 !border-0" />
    </div>
  );
}
