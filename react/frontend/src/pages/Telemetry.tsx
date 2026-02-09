import { memo, useState, useMemo } from 'react'
import useSWR from 'swr'
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock,
  Thermometer,
  Gauge,
  Wind,
  Zap,
  ChevronDown,
  ChevronUp,
  RefreshCw,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

interface AnomalyEvent {
  EVENT_ID: string
  ASSET_ID: string
  TIMESTAMP: string
  ANOMALY_TYPE: string
  ANOMALY_SCORE: number
  SEVERITY: string
  ROOT_CAUSE: string
  SUGGESTED_FIX: string
  RESOLVED: boolean
}

interface CureResult {
  BATCH_ID: string
  AUTOCLAVE_ID: string
  CURE_TIMESTAMP: string
  LAYUP_HUMIDITY_AVG: number
  LAYUP_HUMIDITY_PEAK: number
  SCRAP_FLAG: boolean
  DELAMINATION_SCORE: number
  FAILURE_MODE: string
}

const SEVERITY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  HIGH: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30' },
  MEDIUM: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/30' },
  LOW: { bg: 'bg-green-500/10', text: 'text-green-400', border: 'border-green-500/30' },
}

const ANOMALY_TYPE_ICONS: Record<string, typeof Activity> = {
  HUMIDITY_ALERT: Thermometer,
  PRESSURE_DROP: Gauge,
  VIBRATION_SPIKE: Activity,
  TEMPERATURE_SPIKE: Thermometer,
  DEFAULT: Zap,
}

const StatusBadge = memo(function StatusBadge({ resolved }: { resolved: boolean }) {
  return resolved ? (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-green-500/10 text-green-400">
      <CheckCircle size={12} />
      Resolved
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-amber-500/10 text-amber-400">
      <Clock size={12} />
      Active
    </span>
  )
})

const SeverityBadge = memo(function SeverityBadge({ severity }: { severity: string }) {
  const colors = SEVERITY_COLORS[severity] || SEVERITY_COLORS.LOW
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors.bg} ${colors.text}`}>
      {severity}
    </span>
  )
})

const AnomalyCard = memo(function AnomalyCard({ anomaly }: { anomaly: AnomalyEvent }) {
  const [expanded, setExpanded] = useState(false)
  const Icon = ANOMALY_TYPE_ICONS[anomaly.ANOMALY_TYPE] || ANOMALY_TYPE_ICONS.DEFAULT
  const colors = SEVERITY_COLORS[anomaly.SEVERITY] || SEVERITY_COLORS.LOW

  return (
    <div className={`bg-navy-800/50 rounded-xl border ${colors.border} overflow-hidden`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 text-left flex items-start gap-4 hover:bg-navy-700/30 transition-colors"
      >
        <div className={`p-2 rounded-lg ${colors.bg}`}>
          <Icon size={20} className={colors.text} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-slate-200">{anomaly.ASSET_ID}</span>
            <SeverityBadge severity={anomaly.SEVERITY} />
            <StatusBadge resolved={anomaly.RESOLVED} />
          </div>
          <p className="text-sm text-slate-400">{anomaly.ANOMALY_TYPE.replace(/_/g, ' ')}</p>
          <p className="text-xs text-slate-500 mt-1">
            {new Date(anomaly.TIMESTAMP).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-right">
            <p className="text-sm font-mono text-slate-300">{(anomaly.ANOMALY_SCORE * 100).toFixed(0)}%</p>
            <p className="text-xs text-slate-500">Score</p>
          </div>
          {expanded ? <ChevronUp size={16} className="text-slate-500" /> : <ChevronDown size={16} className="text-slate-500" />}
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-4 border-t border-navy-700/50 pt-3 space-y-3">
          <div>
            <p className="text-xs text-slate-500 mb-1">Root Cause</p>
            <p className="text-sm text-slate-300">{anomaly.ROOT_CAUSE}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">Suggested Fix</p>
            <p className="text-sm text-slate-300">{anomaly.SUGGESTED_FIX}</p>
          </div>
        </div>
      )}
    </div>
  )
})

const HumidityChart = memo(function HumidityChart({ data }: { data: CureResult[] }) {
  const chartData = useMemo(() => {
    return data
      .slice()
      .sort((a, b) => new Date(a.CURE_TIMESTAMP).getTime() - new Date(b.CURE_TIMESTAMP).getTime())
      .map((d) => ({
        time: new Date(d.CURE_TIMESTAMP).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        avg: d.LAYUP_HUMIDITY_AVG,
        peak: d.LAYUP_HUMIDITY_PEAK,
        threshold: 65,
      }))
  }, [data])

  return (
    <ResponsiveContainer width="100%" height={250}>
      <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="humidityGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#29B5E8" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#29B5E8" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="time" stroke="#64748b" fontSize={11} />
        <YAxis stroke="#64748b" fontSize={11} domain={[40, 80]} />
        <Tooltip
          contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
          labelStyle={{ color: '#94a3b8' }}
        />
        <Area type="monotone" dataKey="avg" stroke="#29B5E8" fill="url(#humidityGradient)" name="Avg Humidity %" />
        <Line type="monotone" dataKey="peak" stroke="#f59e0b" strokeWidth={2} dot={false} name="Peak Humidity %" />
        <Line type="monotone" dataKey="threshold" stroke="#ef4444" strokeDasharray="5 5" strokeWidth={1} dot={false} name="Threshold" />
      </AreaChart>
    </ResponsiveContainer>
  )
})

const DelaminationChart = memo(function DelaminationChart({ data }: { data: CureResult[] }) {
  const chartData = useMemo(() => {
    return data
      .slice()
      .sort((a, b) => new Date(a.CURE_TIMESTAMP).getTime() - new Date(b.CURE_TIMESTAMP).getTime())
      .map((d) => ({
        batch: d.BATCH_ID.replace('BATCH-', ''),
        score: d.DELAMINATION_SCORE,
        scrap: d.SCRAP_FLAG ? d.DELAMINATION_SCORE : null,
      }))
  }, [data])

  return (
    <ResponsiveContainer width="100%" height={250}>
      <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="batch" stroke="#64748b" fontSize={10} angle={-45} textAnchor="end" height={60} />
        <YAxis stroke="#64748b" fontSize={11} domain={[0, 60]} />
        <Tooltip
          contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
          labelStyle={{ color: '#94a3b8' }}
        />
        <Line type="monotone" dataKey="score" stroke="#8b5cf6" strokeWidth={2} dot={{ fill: '#8b5cf6', r: 3 }} name="Delamination Score" />
        <Line type="monotone" dataKey="scrap" stroke="#ef4444" strokeWidth={0} dot={{ fill: '#ef4444', r: 6 }} name="Scrapped Batch" />
      </LineChart>
    </ResponsiveContainer>
  )
})

const StatCard = memo(function StatCard({
  icon: Icon,
  label,
  value,
  subtext,
  trend,
}: {
  icon: typeof Activity
  label: string
  value: string | number
  subtext?: string
  trend?: 'up' | 'down' | 'neutral'
}) {
  const trendColors = {
    up: 'text-red-400',
    down: 'text-green-400',
    neutral: 'text-slate-400',
  }

  return (
    <div className="bg-navy-800/50 rounded-xl p-4 border border-navy-700/50">
      <div className="flex items-center gap-3 mb-2">
        <div className="p-2 rounded-lg bg-accent-blue/10">
          <Icon size={18} className="text-accent-blue" />
        </div>
        <span className="text-sm text-slate-400">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${trend ? trendColors[trend] : 'text-slate-200'}`}>{value}</p>
      {subtext && <p className="text-xs text-slate-500 mt-1">{subtext}</p>}
    </div>
  )
})

export default function Telemetry() {
  const [autoRefresh, setAutoRefresh] = useState(true)
  const refreshInterval = autoRefresh ? 5000 : 0

  const { data: anomalyData, isLoading: anomalyLoading, mutate: refetchAnomalies } = useSWR(
    `${API_BASE}/api/anomaly-events`,
    fetcher,
    { refreshInterval }
  )

  const { data: cureData, isLoading: cureLoading, mutate: refetchCure } = useSWR(
    `${API_BASE}/api/cure-results`,
    fetcher,
    { refreshInterval }
  )

  const anomalies: AnomalyEvent[] = anomalyData?.events || []
  const cureResults: CureResult[] = cureData?.results || []

  const stats = useMemo(() => {
    const activeAnomalies = anomalies.filter((a) => !a.RESOLVED).length
    const highSeverity = anomalies.filter((a) => a.SEVERITY === 'HIGH' && !a.RESOLVED).length
    const scrapRate = cureResults.length > 0
      ? (cureResults.filter((c) => c.SCRAP_FLAG).length / cureResults.length) * 100
      : 0
    const avgHumidity = cureResults.length > 0
      ? cureResults.reduce((sum, c) => sum + c.LAYUP_HUMIDITY_AVG, 0) / cureResults.length
      : 0

    return { activeAnomalies, highSeverity, scrapRate, avgHumidity }
  }, [anomalies, cureResults])

  const handleRefresh = () => {
    refetchAnomalies()
    refetchCure()
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-200">Asset Telemetry</h1>
          <p className="text-slate-400 text-sm mt-1">Real-time sensor data and anomaly detection</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-navy-600 bg-navy-700 text-accent-blue focus:ring-accent-blue"
            />
            Auto-refresh (5s)
          </label>
          <button
            onClick={handleRefresh}
            className="flex items-center gap-2 px-4 py-2 bg-navy-700 hover:bg-navy-600 rounded-lg text-sm text-slate-300 transition-colors"
          >
            <RefreshCw size={16} className={autoRefresh ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <StatCard
          icon={AlertTriangle}
          label="Active Anomalies"
          value={stats.activeAnomalies}
          subtext={`${stats.highSeverity} high severity`}
          trend={stats.highSeverity > 0 ? 'up' : 'neutral'}
        />
        <StatCard
          icon={Wind}
          label="Avg Humidity"
          value={`${stats.avgHumidity.toFixed(1)}%`}
          subtext="Layup room average"
          trend={stats.avgHumidity > 60 ? 'up' : 'neutral'}
        />
        <StatCard
          icon={Activity}
          label="Scrap Rate"
          value={`${stats.scrapRate.toFixed(1)}%`}
          subtext={`${cureResults.filter((c) => c.SCRAP_FLAG).length} of ${cureResults.length} batches`}
          trend={stats.scrapRate > 10 ? 'up' : 'down'}
        />
        <StatCard
          icon={CheckCircle}
          label="Batches Processed"
          value={cureResults.length}
          subtext="Cure cycle results"
        />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-navy-800/50 rounded-xl p-4 border border-navy-700/50">
          <h3 className="text-sm font-medium text-slate-300 mb-4">Layup Room Humidity Trend</h3>
          {cureLoading ? (
            <div className="h-[250px] flex items-center justify-center">
              <div className="animate-pulse text-slate-500">Loading...</div>
            </div>
          ) : (
            <HumidityChart data={cureResults} />
          )}
        </div>

        <div className="bg-navy-800/50 rounded-xl p-4 border border-navy-700/50">
          <h3 className="text-sm font-medium text-slate-300 mb-4">Delamination Score by Batch</h3>
          {cureLoading ? (
            <div className="h-[250px] flex items-center justify-center">
              <div className="animate-pulse text-slate-500">Loading...</div>
            </div>
          ) : (
            <DelaminationChart data={cureResults} />
          )}
        </div>
      </div>

      <div>
        <h3 className="text-lg font-medium text-slate-300 mb-4">Anomaly Events</h3>
        {anomalyLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-navy-800/50 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : anomalies.length === 0 ? (
          <div className="bg-navy-800/50 rounded-xl p-8 text-center border border-navy-700/50">
            <CheckCircle size={32} className="mx-auto text-green-400 mb-2" />
            <p className="text-slate-400">No anomaly events detected</p>
          </div>
        ) : (
          <div className="space-y-3">
            {anomalies.map((anomaly) => (
              <AnomalyCard key={anomaly.EVENT_ID} anomaly={anomaly} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
