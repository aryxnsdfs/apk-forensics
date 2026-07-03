import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { useSimulationState } from '../../store/simulationStore';

export default function RewardCurve() {
  const { rewardHistory } = useSimulationState();

  const latest = rewardHistory.length > 0
    ? rewardHistory[rewardHistory.length - 1]?.reward
    : null;

  return (
    <div className="panel-card p-3 h-full flex flex-col">
      <div className="relative z-10 flex items-center justify-between mb-2">
        <span className="text-[10px] font-semibold prism-title uppercase tracking-wider">
          Evaluator Reward Trace
        </span>
        <span className="text-[10px] forensic-token text-blue-200">
          {latest !== null ? `Total: ${latest.toFixed(2)}` : 'Awaiting Evidence'}
        </span>
      </div>
      <div className="relative z-10 flex-1 min-h-0">
        {rewardHistory.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <div className="black-button w-10 h-10 mx-auto mb-2 rounded-xl flex items-center justify-center">
                <svg className="w-5 h-5 text-zinc-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <polyline points="22,12 18,12 15,21 9,3 6,12 2,12" />
                </svg>
              </div>
              <p className="text-[10px] text-zinc-600 font-mono">Chart updates from active GRPO forensic evaluation steps.</p>
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={rewardHistory} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
              <defs>
                <linearGradient id="rewardGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#60a5fa" stopOpacity={0.34} />
                  <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="episode"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 9, fill: '#52525b' }}
                label={{ value: 'Evaluator Event', position: 'insideBottom', offset: -2, fontSize: 9, fill: '#52525b' }}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 9, fill: '#52525b' }}
              />
              <ReferenceLine y={0} stroke="#3f3f46" strokeDasharray="3 3" />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(10, 12, 20, 0.92)',
                  border: '1px solid rgba(147, 197, 253, 0.22)',
                  borderRadius: '12px',
                  fontSize: '10px',
                  fontFamily: 'JetBrains Mono, monospace',
                  color: '#a1a1aa',
                }}
                formatter={(value) => [value.toFixed(2), 'Reward']}
                labelFormatter={(label) => `Event ${label}`}
              />
              <Area
                type="linear"
                dataKey="reward"
                stroke="#60a5fa"
                strokeWidth={2}
                fill="url(#rewardGradient)"
                dot={false}
                activeDot={{ r: 3, fill: '#93c5fd', stroke: '#111827', strokeWidth: 2 }}
                isAnimationActive={true}
                animationDuration={400}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
