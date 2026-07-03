import { useEffect, useMemo, useRef } from 'react';
import ReactFlow, { Background, Controls, useNodesState, useEdgesState } from 'reactflow';
import 'reactflow/dist/style.css';
import { useSimulationState } from '../../store/simulationStore';
import CustomNode from './CustomNode';

const nodeTypes = { custom: CustomNode };
const NODE_SPACING_X = 340; // horizontal gap between siblings
const LAYER_SPACING_Y = 140; // vertical gap between causal depths
const LAYOUT_MARGIN_X = 40;
const LAYOUT_MARGIN_Y = 28;

// Top-down layered DAG: causal depth = vertical layer, siblings spread
// horizontally and centered. Fills wide panels; disconnected nodes -> layer 0.
function buildWrappedLayout(nodes, edges) {
  const indeg = new Map();
  const adj = new Map();
  nodes.forEach((n) => { indeg.set(n.id, 0); adj.set(n.id, []); });
  edges.forEach((e) => {
    if (!adj.has(e.source) || !indeg.has(e.target)) return;
    adj.get(e.source).push(e.target);
    indeg.set(e.target, (indeg.get(e.target) || 0) + 1);
  });

  // Kahn topological order + longest-path depth.
  const depth = new Map(nodes.map((n) => [n.id, 0]));
  const work = new Map(indeg);
  const queue = nodes.filter((n) => (indeg.get(n.id) || 0) === 0).map((n) => n.id);
  const order = [];
  const seen = new Set();
  while (queue.length > 0) {
    const u = queue.shift();
    if (seen.has(u)) continue;
    seen.add(u);
    order.push(u);
    (adj.get(u) || []).forEach((v) => {
      depth.set(v, Math.max(depth.get(v) || 0, (depth.get(u) || 0) + 1));
      work.set(v, (work.get(v) || 1) - 1);
      if ((work.get(v) || 0) <= 0) queue.push(v);
    });
  }
  nodes.forEach((n) => { if (!seen.has(n.id)) order.push(n.id); });

  const layers = new Map();
  order.forEach((id) => {
    const d = depth.get(id) || 0;
    if (!layers.has(d)) layers.set(d, []);
    layers.get(d).push(id);
  });

  const rawPos = new Map();
  let minX = 0;
  layers.forEach((layer, d) => {
    const layerWidth = (layer.length - 1) * NODE_SPACING_X;
    layer.forEach((id, index) => {
      const x = index * NODE_SPACING_X - layerWidth / 2;
      minX = Math.min(minX, x);
      rawPos.set(id, { x, y: d * LAYER_SPACING_Y });
    });
  });
  const xShift = LAYOUT_MARGIN_X - minX;

  return nodes.map((node) => {
    const p = rawPos.get(node.id) || { x: 0, y: 0 };
    return {
      ...node,
      position: { x: xShift + p.x, y: LAYOUT_MARGIN_Y + p.y },
    };
  });
}

export default function CausalDAG() {
  const { causalNodes, causalEdges } = useSimulationState();
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const reactFlowRef = useRef(null);

  const layoutNodes = useMemo(
    () => buildWrappedLayout(causalNodes, causalEdges),
    [causalNodes, causalEdges]
  );

  useEffect(() => {
    setNodes(layoutNodes);
    setEdges(causalEdges);
  }, [layoutNodes, causalEdges, setNodes, setEdges]);

  useEffect(() => {
    if (!reactFlowRef.current || layoutNodes.length === 0) return;
    const timeout = setTimeout(() => {
      reactFlowRef.current.fitView({
        padding: 0.12,
        duration: 300,
        minZoom: 0.28,
        maxZoom: 1.45,
      });
    }, 50);
    return () => clearTimeout(timeout);
  }, [layoutNodes, causalEdges]);

  return (
    <div className="panel-card h-full flex flex-col overflow-hidden">
      <div className="relative z-10 flex items-center justify-between px-3 py-2 border-b border-white/10 shrink-0">
        <div className="flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5 text-blue-300" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="4" cy="4" r="2" />
            <circle cx="12" cy="12" r="2" />
            <circle cx="12" cy="4" r="2" />
            <line x1="6" y1="4" x2="10" y2="4" />
            <line x1="12" y1="6" x2="12" y2="10" />
          </svg>
          <span className="text-[10px] font-semibold prism-title uppercase tracking-wider">
            Attack Graph
          </span>
        </div>
        <span className="text-[9px] forensic-token text-zinc-600">
          {causalNodes.length} nodes / {causalEdges.length} edges
        </span>
      </div>
      <div className="relative z-10 flex-1 min-h-0">
        {causalNodes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-zinc-600">
            <svg className="w-8 h-8 text-zinc-700 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="5" cy="6" r="3" />
              <circle cx="19" cy="6" r="3" />
              <circle cx="12" cy="18" r="3" />
              <line x1="7.5" y1="7.5" x2="10" y2="15.5" />
              <line x1="16.5" y1="7.5" x2="14" y2="15.5" />
            </svg>
            <p className="text-[10px] forensic-token">Attack graph builds during analysis...</p>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onInit={(instance) => { reactFlowRef.current = instance; }}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.12, minZoom: 0.28, maxZoom: 1.45 }}
            minZoom={0.25}
            maxZoom={2.0}
            nodesDraggable
            panOnDrag
            proOptions={{ hideAttribution: true }}
          >
            <Background color="rgba(147,197,253,0.16)" gap={22} size={1} />
            <Controls
              showInteractive={false}
            />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}
