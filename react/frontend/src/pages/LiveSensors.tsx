import { memo, useState, useMemo, useEffect } from 'react'
import useSWR from 'swr'
import {
  Activity,
  Thermometer,
  Gauge,
  Wind,
  Radio,
  RefreshCw,
  ChevronDown,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

interface AssetSensorData {
  ASSET_ID: string
  EVENT_TIME: string
  TEMPERATURE_C: number | null
  PRESSURE_PSI: number | null
  HUMIDITY_PCT: number | null
  VIBRATION_G: number | null
  VACUUM_MBAR: number | null
  INGESTION_TIME: string
}

interface SensorHistory {
  time: string
  value: number
}

const SENSOR_CONFIG: Record<string, { label: string; unit: string; color: string; icon: typeof Activity }> = {
  temperature: { label: 'Temperature', unit: '°C', color: '#ef4444', icon: Thermometer },
  humidity: { label: 'Humidity', unit: '%', color: '#3b82f6', icon: Wind },
  pressure: { label: 'Pressure', unit: 'PSI', color: '#f59e0b', icon: Gauge },
  vibration: { label: 'Vibration', unit: 'G', color: '#22c55e', icon: Activity },
  vacuum: { label: 'Vacuum', unit: 'mbar', color: '#8b5cf6', icon: Gauge },
}

const SENSOR_KEYS = ['temperature', 'humidity', 'pressure', 'vibration', 'vacuum'] as const
type SensorKey = typeof SENSOR_KEYS[number]

const SensorStreamChart = memo(function SensorStreamChart({
  assetId,
  sensorKey,
  data,
  timestamp,
}: {
  assetId: string
  sensorKey: SensorKey
  data: AssetSensorData[]
  timestamp: string | null
}) {
  const [history, setHistory] = useState<SensorHistory[]>([])
  const config = SENSOR_CONFIG[sensorKey]

  const getValueForSensor = (d: AssetSensorData, key: SensorKey): number | null => {
    switch (key) {
      case 'temperature': return d.TEMPERATURE_C
      case 'humidity': return d.HUMIDITY_PCT
      case 'pressure': return d.PRESSURE_PSI
      case 'vibration': return d.VIBRATION_G
      case 'vacuum': return d.VACUUM_MBAR
      default: return null
    }
  }

  useEffect(() => {
    if (!data || data.length === 0) return

    const assetData = data.filter(d => d.ASSET_ID === assetId)
    if (assetData.length === 0) return

    const values = assetData.map(d => getValueForSensor(d, sensorKey)).filter((v): v is number => v !== null)
    if (values.length === 0) return

    const avgValue = values.reduce((sum, v) => sum + v, 0) / values.length
    const timeStr = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString()

    setHistory(prev => {
      const next = [...prev, { time: timeStr, value: avgValue }]
      return next.slice(-30)
    })
  }, [data, timestamp, assetId, sensorKey])

  const currentValue = history.length > 0 ? history[history.length - 1].value : null

  return (
    <div className="bg-navy-900/50 rounded-lg p-3 border border-navy-700/30">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <config.icon size={14} style={{ color: config.color }} />
          <span className="text-xs text-slate-400">{config.label}</span>
        </div>
        {currentValue !== null && (
          <span className="text-sm font-mono font-bold" style={{ color: config.color }}>
            {currentValue.toFixed(sensorKey === 'vibration' ? 2 : 1)} {config.unit}
          </span>
        )}
      </div>
      {history.length > 1 ? (
        <ResponsiveContainer width="100%" height={80}>
          <LineChart data={history} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
            <XAxis dataKey="time" hide />
            <YAxis hide domain={['auto', 'auto']} />
            <Tooltip
              contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '4px', fontSize: '10px' }}
              labelStyle={{ color: '#94a3b8' }}
              formatter={(value: number) => [`${value.toFixed(2)} ${config.unit}`, config.label]}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={config.color}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="h-[80px] flex items-center justify-center text-xs text-slate-600">
          Waiting for data...
        </div>
      )}
    </div>
  )
})

const AssetCard = memo(function AssetCard({
  assetId,
  data,
  timestamp,
  selectedSensors,
}: {
  assetId: string
  data: AssetSensorData[]
  timestamp: string | null
  selectedSensors: SensorKey[]
}) {
  const [expanded, setExpanded] = useState(true)
  const assetData = useMemo(() => data.filter(d => d.ASSET_ID === assetId), [data, assetId])
  
  const hasData = assetData.length > 0
  const latestReading = assetData[0]

  const availableSensors = useMemo(() => {
    if (!latestReading) return []
    return selectedSensors.filter(key => {
      switch (key) {
        case 'temperature': return latestReading.TEMPERATURE_C !== null
        case 'humidity': return latestReading.HUMIDITY_PCT !== null
        case 'pressure': return latestReading.PRESSURE_PSI !== null
        case 'vibration': return latestReading.VIBRATION_G !== null
        case 'vacuum': return latestReading.VACUUM_MBAR !== null
        default: return false
      }
    })
  }, [latestReading, selectedSensors])

  return (
    <div className="bg-navy-800/50 rounded-xl border border-navy-700/50 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-navy-700/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`w-2 h-2 rounded-full ${hasData ? 'bg-green-400 animate-pulse' : 'bg-slate-600'}`} />
          <span className="font-medium text-slate-200">{assetId}</span>
          <span className="text-xs text-slate-500">
            {availableSensors.length} sensor{availableSensors.length !== 1 ? 's' : ''}
          </span>
        </div>
        <ChevronDown size={16} className={`text-slate-500 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>
      {expanded && (
        <div className="px-4 pb-4">
          {availableSensors.length > 0 ? (
            <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
              {availableSensors.map(sensorKey => (
                <SensorStreamChart
                  key={`${assetId}-${sensorKey}`}
                  assetId={assetId}
                  sensorKey={sensorKey}
                  data={data}
                  timestamp={timestamp}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-6 text-sm text-slate-500">
              No sensor data available for selected sensors
            </div>
          )}
        </div>
      )}
    </div>
  )
})

export default function LiveSensors() {
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [selectedSensors, setSelectedSensors] = useState<SensorKey[]>(['temperature', 'humidity', 'pressure', 'vibration', 'vacuum'])
  const refreshInterval = autoRefresh ? 1000 : 0

  const { data: sensorData, isLoading, mutate } = useSWR(
    `${API_BASE}/api/live-sensors-by-asset`,
    fetcher,
    { refreshInterval }
  )

  const liveSensors: AssetSensorData[] = sensorData?.sensors || []
  const sensorTimestamp: string | null = sensorData?.timestamp || null

  const assets = useMemo(() => {
    const assetsWithData = liveSensors.reduce((acc, sensor) => {
      const hasSensorData = 
        sensor.TEMPERATURE_C !== null ||
        sensor.HUMIDITY_PCT !== null ||
        sensor.PRESSURE_PSI !== null ||
        sensor.VIBRATION_G !== null ||
        sensor.VACUUM_MBAR !== null
      if (hasSensorData) {
        acc.add(sensor.ASSET_ID)
      }
      return acc
    }, new Set<string>())
    return Array.from(assetsWithData).sort()
  }, [liveSensors])

  const toggleSensor = (key: SensorKey) => {
    setSelectedSensors(prev => 
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-200">Live Sensor Stream</h1>
          <p className="text-slate-400 text-sm mt-1">Real-time sensor data by asset</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-navy-600 bg-navy-700 text-accent-blue focus:ring-accent-blue"
            />
            Auto-refresh (1s)
          </label>
          <button
            onClick={() => mutate()}
            className="flex items-center gap-2 px-4 py-2 bg-navy-700 hover:bg-navy-600 rounded-lg text-sm text-slate-300 transition-colors"
          >
            <RefreshCw size={16} className={autoRefresh ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      <div className="bg-navy-800/50 rounded-xl p-4 border border-navy-700/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Radio size={16} className="text-accent-blue" />
              <span className="text-sm text-slate-300">Sensor Filters</span>
            </div>
            <div className="flex items-center gap-2">
              {SENSOR_KEYS.map(key => {
                const config = SENSOR_CONFIG[key]
                const isSelected = selectedSensors.includes(key)
                return (
                  <button
                    key={key}
                    onClick={() => toggleSensor(key)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
                      isSelected
                        ? 'bg-accent-blue/20 text-accent-blue border border-accent-blue/30'
                        : 'bg-navy-700 text-slate-400 border border-navy-600 hover:border-navy-500'
                    }`}
                  >
                    <config.icon size={12} />
                    {config.label}
                  </button>
                )
              })}
            </div>
          </div>
          <div className="flex items-center gap-3">
            {autoRefresh && (
              <span className="flex items-center gap-1.5 text-xs text-green-400">
                <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                Streaming
              </span>
            )}
            {sensorTimestamp && (
              <span className="text-xs text-slate-500">
                Last update: {new Date(sensorTimestamp).toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
      </div>

      {isLoading && assets.length === 0 ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-40 bg-navy-800/50 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : assets.length === 0 ? (
        <div className="bg-navy-800/50 rounded-xl p-12 text-center border border-navy-700/50">
          <Radio size={40} className="mx-auto text-slate-600 mb-3" />
          <p className="text-slate-400">No live sensor data available</p>
          <p className="text-sm text-slate-500 mt-1">Waiting for data from streaming sensors...</p>
        </div>
      ) : (
        <div className="space-y-4">
          {assets.map(assetId => (
            <AssetCard
              key={assetId}
              assetId={assetId}
              data={liveSensors}
              timestamp={sensorTimestamp}
              selectedSensors={selectedSensors}
            />
          ))}
        </div>
      )}
    </div>
  )
}
