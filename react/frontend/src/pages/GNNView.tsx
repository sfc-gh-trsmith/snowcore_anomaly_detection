import { memo, useMemo, useState, useEffect } from 'react'
import { Info, RefreshCw } from 'lucide-react'

interface GNNNode {
  id: string
  x: number
  y: number
  impact: number
  role: string
  anomalySource: string
  propagationReason: string
  riskFactors: string[]
  mtbfImpact: string
  upstream: string[] | null
  downstream: string[] | null
}

const DEFAULT_NODES: GNNNode[] = [
  {
    id: 'LAYUP_ROOM',
    x: 0,
    y: 1,
    impact: 0.8,
    role: 'Source Node',
    anomalySource: 'Temperature deviation (+2.3°C)',
    propagationReason: 'Environmental conditions affect composite material properties',
    riskFactors: ['Humidity sensor drift', 'HVAC load imbalance'],
    mtbfImpact: '-15% estimated',
    upstream: null,
    downstream: ['LAYUP_BOT_01', 'LAYUP_BOT_02'],
  },
  {
    id: 'LAYUP_BOT_01',
    x: 1,
    y: 0,
    impact: 0.6,
    role: 'Processing Node',
    anomalySource: 'Inherited from LAYUP_ROOM',
    propagationReason: 'Material quality variance affects layup precision',
    riskFactors: ['Ply alignment deviation', 'Resin distribution'],
    mtbfImpact: '-12% estimated',
    upstream: ['LAYUP_ROOM'],
    downstream: ['AUTOCLAVE_01'],
  },
  {
    id: 'LAYUP_BOT_02',
    x: 1,
    y: 2,
    impact: 0.3,
    role: 'Processing Node',
    anomalySource: 'Minimal exposure',
    propagationReason: 'Operating on different material batch',
    riskFactors: ['Low correlation with current anomaly'],
    mtbfImpact: '-3% estimated',
    upstream: ['LAYUP_ROOM'],
    downstream: ['AUTOCLAVE_02'],
  },
  {
    id: 'AUTOCLAVE_01',
    x: 2,
    y: 0,
    impact: 0.9,
    role: 'Critical Node',
    anomalySource: 'Pressure cycle variance detected',
    propagationReason: 'Upstream material issues + own sensor anomaly compound risk',
    riskFactors: ['Cure cycle deviation', 'Thermocouple drift', 'Door seal wear'],
    mtbfImpact: '-22% estimated',
    upstream: ['LAYUP_BOT_01'],
    downstream: ['CNC_MILL_01'],
  },
  {
    id: 'AUTOCLAVE_02',
    x: 2,
    y: 2,
    impact: 0.2,
    role: 'Processing Node',
    anomalySource: 'None detected',
    propagationReason: 'Isolated from primary anomaly chain',
    riskFactors: ['Nominal operation'],
    mtbfImpact: '0% (baseline)',
    upstream: ['LAYUP_BOT_02'],
    downstream: ['CNC_MILL_02'],
  },
  {
    id: 'CNC_MILL_01',
    x: 3,
    y: 0,
    impact: 0.7,
    role: 'Processing Node',
    anomalySource: 'Spindle vibration +0.8mm/s',
    propagationReason: 'Cured part variance affects machining parameters',
    riskFactors: ['Tool wear acceleration', 'Surface finish deviation'],
    mtbfImpact: '-18% estimated',
    upstream: ['AUTOCLAVE_01'],
    downstream: ['QC_STATION_01'],
  },
  {
    id: 'CNC_MILL_02',
    x: 3,
    y: 2,
    impact: 0.1,
    role: 'Processing Node',
    anomalySource: 'None detected',
    propagationReason: 'Isolated from primary anomaly chain',
    riskFactors: ['Nominal operation'],
    mtbfImpact: '0% (baseline)',
    upstream: ['AUTOCLAVE_02'],
    downstream: ['QC_STATION_02'],
  },
  {
    id: 'QC_STATION_01',
    x: 4,
    y: 0,
    impact: 0.5,
    role: 'Sink Node',
    anomalySource: 'Increased rejection rate predicted',
    propagationReason: 'Cumulative upstream variance exceeds tolerance',
    riskFactors: ['Dimensional variance', 'Surface defects', 'Delamination risk'],
    mtbfImpact: 'N/A (quality gate)',
    upstream: ['CNC_MILL_01'],
    downstream: null,
  },
  {
    id: 'QC_STATION_02',
    x: 4,
    y: 2,
    impact: 0.1,
    role: 'Sink Node',
    anomalySource: 'None detected',
    propagationReason: 'Clean upstream chain',
    riskFactors: ['Nominal rejection rate expected'],
    mtbfImpact: 'N/A (quality gate)',
    upstream: ['CNC_MILL_02'],
    downstream: null,
  },
]

const EDGES: [string, string][] = [
  ['LAYUP_ROOM', 'LAYUP_BOT_01'],
  ['LAYUP_ROOM', 'LAYUP_BOT_02'],
  ['LAYUP_BOT_01', 'AUTOCLAVE_01'],
  ['LAYUP_BOT_02', 'AUTOCLAVE_02'],
  ['AUTOCLAVE_01', 'CNC_MILL_01'],
  ['AUTOCLAVE_02', 'CNC_MILL_02'],
  ['CNC_MILL_01', 'QC_STATION_01'],
  ['CNC_MILL_02', 'QC_STATION_02'],
]

function useGNNData() {
  const [nodes, setNodes] = useState<GNNNode[]>(DEFAULT_NODES)
  const [loading, setLoading] = useState(false)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await fetch('http://localhost:8000/api/gnn-propagation')
      if (res.ok) {
        const data = await res.json()
        if (data.nodes && data.nodes.length > 0) {
          const scoreMap = new Map(data.nodes.map((n: { ASSET: string; SCORE: number }) => [n.ASSET, n.SCORE]))
          setNodes(
            DEFAULT_NODES.map((node) => ({
              ...node,
              impact: scoreMap.get(node.id) ?? node.impact,
            }))
          )
          setLastUpdate(new Date())
        }
      }
    } catch (e) {
      console.error('Failed to fetch GNN data:', e)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchData()
  }, [])

  return { nodes, loading, lastUpdate, refresh: fetchData }
}

const NodeDetail = memo(function NodeDetail({ node }: { node: GNNNode | null }) {
  if (!node) {
    return (
      <div className="card h-full flex items-center justify-center text-slate-500">
        <p>Select a node to view details</p>
      </div>
    )
  }

  const impactColor =
    node.impact > 0.7 ? 'text-accent-red' : node.impact > 0.4 ? 'text-accent-yellow' : 'text-accent-green'

  return (
    <div className="card h-full overflow-auto">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-200">{node.id}</h3>
          <span className="text-sm text-slate-400">{node.role}</span>
        </div>
        <div className={`text-3xl font-bold ${impactColor}`}>{Math.round(node.impact * 100)}%</div>
      </div>

      <div className="space-y-4">
        <div>
          <h4 className="text-sm font-medium text-slate-400 mb-1">Anomaly Source</h4>
          <p className="text-slate-200">{node.anomalySource}</p>
        </div>

        <div>
          <h4 className="text-sm font-medium text-slate-400 mb-1">Propagation Reason</h4>
          <p className="text-slate-200">{node.propagationReason}</p>
        </div>

        <div>
          <h4 className="text-sm font-medium text-slate-400 mb-1">MTBF Impact</h4>
          <p className={node.mtbfImpact.startsWith('-') ? 'text-accent-red' : 'text-slate-200'}>
            {node.mtbfImpact}
          </p>
        </div>

        <div>
          <h4 className="text-sm font-medium text-slate-400 mb-1">Risk Factors</h4>
          <ul className="space-y-1">
            {node.riskFactors.map((factor, i) => (
              <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                <span className="text-accent-blue mt-1">•</span>
                {factor}
              </li>
            ))}
          </ul>
        </div>

        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-navy-700/50">
          <div>
            <h4 className="text-sm font-medium text-slate-400 mb-1">Upstream</h4>
            <p className="text-slate-300">{node.upstream?.join(', ') || 'None (source)'}</p>
          </div>
          <div>
            <h4 className="text-sm font-medium text-slate-400 mb-1">Downstream</h4>
            <p className="text-slate-300">{node.downstream?.join(', ') || 'None (sink)'}</p>
          </div>
        </div>
      </div>
    </div>
  )
})

const GNNGraph = memo(function GNNGraph({
  nodes,
  edges,
  selectedNode,
  onSelectNode,
}: {
  nodes: GNNNode[]
  edges: [string, string][]
  selectedNode: string | null
  onSelectNode: (id: string) => void
}) {
  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes])

  const scale = 120
  const offsetX = 60
  const offsetY = 60
  const nodeRadius = 30
  const width = 5 * scale + offsetX * 2
  const height = 3 * scale + offsetY * 2

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
      <defs>
        {edges.map(([src, tgt]) => {
          const srcNode = nodeMap.get(src)!
          const tgtNode = nodeMap.get(tgt)!
          const strength = Math.max(srcNode.impact, tgtNode.impact)
          const markerId = `arrow-${src}-${tgt}`
          return (
            <marker
              key={markerId}
              id={markerId}
              viewBox="0 0 10 10"
              refX="10"
              refY="5"
              markerWidth={4 + strength * 2}
              markerHeight={4 + strength * 2}
              orient="auto-start-reverse"
            >
              <path
                d="M 0 0 L 10 5 L 0 10 z"
                fill={`rgba(41, 181, 232, ${Math.max(strength, 0.5)})`}
              />
            </marker>
          )
        })}
      </defs>

      {edges.map(([src, tgt]) => {
        const srcNode = nodeMap.get(src)!
        const tgtNode = nodeMap.get(tgt)!
        const strength = Math.max(srcNode.impact, tgtNode.impact)

        const x1 = srcNode.x * scale + offsetX
        const y1 = srcNode.y * scale + offsetY
        const x2 = tgtNode.x * scale + offsetX
        const y2 = tgtNode.y * scale + offsetY

        const dx = x2 - x1
        const dy = y2 - y1
        const len = Math.sqrt(dx * dx + dy * dy)
        const ux = dx / len
        const uy = dy / len

        const startX = x1 + ux * nodeRadius
        const startY = y1 + uy * nodeRadius
        const endX = x2 - ux * (nodeRadius + 8)
        const endY = y2 - uy * (nodeRadius + 8)

        return (
          <line
            key={`${src}-${tgt}`}
            x1={startX}
            y1={startY}
            x2={endX}
            y2={endY}
            stroke={`rgba(41, 181, 232, ${strength})`}
            strokeWidth={2 + strength * 4}
            markerEnd={`url(#arrow-${src}-${tgt})`}
          />
        )
      })}

      {nodes.map((node) => {
        const cx = node.x * scale + offsetX
        const cy = node.y * scale + offsetY
        const r = node.impact * 255
        const g = (1 - node.impact) * 200
        const b = (1 - node.impact) * 100
        const isSelected = selectedNode === node.id

        return (
          <g key={node.id} className="cursor-pointer" onClick={() => onSelectNode(node.id)}>
            <circle
              cx={cx}
              cy={cy}
              r={30}
              fill={`rgb(${r}, ${g}, ${b})`}
              stroke={isSelected ? '#29B5E8' : 'white'}
              strokeWidth={isSelected ? 4 : 2}
              className="transition-all"
            />
            <text
              x={cx}
              y={cy - 5}
              textAnchor="middle"
              fill="white"
              fontSize="9"
              fontWeight="500"
            >
              {node.id.split('_')[0]}
            </text>
            <text x={cx} y={cy + 8} textAnchor="middle" fill="white" fontSize="10" fontWeight="bold">
              {Math.round(node.impact * 100)}%
            </text>
          </g>
        )
      })}
    </svg>
  )
})

export default function GNNView() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [showHelp, setShowHelp] = useState(false)
  const { nodes, loading, lastUpdate, refresh } = useGNNData()
  const selectedNode = nodes.find((n) => n.id === selectedNodeId) || null

  return (
    <div className="p-6 space-y-6 h-full flex flex-col">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">GNN Anomaly Propagation</h1>
          <p className="text-slate-400 mt-1">
            Predicted impact flow based on asset dependencies
            {lastUpdate && (
              <span className="ml-2 text-xs text-slate-500">
                (Updated: {lastUpdate.toLocaleTimeString()})
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={refresh}
            disabled={loading}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={() => setShowHelp(!showHelp)}
            className="btn-secondary flex items-center gap-2"
            aria-expanded={showHelp}
          >
            <Info size={16} />
            How it Works
          </button>
        </div>
      </div>

      {showHelp && (
        <div className="card bg-accent-blue/5 border-accent-blue/30">
          <h3 className="font-semibold text-slate-200 mb-2">How GNN Propagation Works</h3>
          <div className="text-sm text-slate-300 space-y-2">
            <p>
              <strong>Graph Neural Networks (GNNs)</strong> model how anomalies spread through interconnected
              manufacturing assets.
            </p>
            <ul className="list-disc list-inside space-y-1 text-slate-400">
              <li>
                <strong>Asset Graph:</strong> Nodes are assets, edges represent dependencies (material flow,
                shared utilities)
              </li>
              <li>
                <strong>Message Passing:</strong> Risk propagates based on connection strength and historical
                correlation
              </li>
              <li>
                <strong>Impact Score:</strong> Probability of degraded performance given upstream anomalies
              </li>
            </ul>
            <p className="pt-2">
              <strong>Reading the Graph:</strong> Red = high risk, Green = low risk. Edge thickness shows
              propagation strength. Click a node for details.
            </p>
          </div>
        </div>
      )}

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 min-h-0">
        <div className="lg:col-span-2 card p-4">
          <GNNGraph
            nodes={nodes}
            edges={EDGES}
            selectedNode={selectedNodeId}
            onSelectNode={setSelectedNodeId}
          />
        </div>
        <div className="min-h-[400px]">
          <NodeDetail node={selectedNode} />
        </div>
      </div>
    </div>
  )
}
