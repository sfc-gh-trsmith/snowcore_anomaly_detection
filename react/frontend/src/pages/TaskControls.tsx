import { useState } from 'react'
import useSWR from 'swr'
import {
  Play,
  Pause,
  RefreshCw,
  Zap,
  Activity,
  Trash2,
  Clock,
  AlertTriangle,
} from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

interface TaskStatus {
  name: string
  state: string
  schedule: string | null
  warehouse: string | null
  last_run: string | null
}

interface AnomalyTrigger {
  asset_id: string
  trigger_active: boolean
  triggered_at: string | null
  triggered_by: string | null
}

const SIMULATION_ASSETS = [
  'LAYUP_ROOM',
  'AUTOCLAVE_01',
  'AUTOCLAVE_02',
  'CNC_MILL_01',
  'CNC_MILL_02',
  'LAYUP_BOT_01',
  'LAYUP_BOT_02',
]

export default function TaskControls() {
  const [isToggling, setIsToggling] = useState(false)
  const [isInjecting, setIsInjecting] = useState(false)

  const { data: taskData, mutate: mutateTasks } = useSWR<{ tasks: TaskStatus[] }>(
    `${API_BASE}/api/task-status`,
    fetcher,
    { refreshInterval: 5000 }
  )

  const { data: triggerData, mutate: mutateTriggers } = useSWR<{ triggers: AnomalyTrigger[] }>(
    `${API_BASE}/api/anomaly-triggers`,
    fetcher,
    { refreshInterval: 5000 }
  )

  const tasks = taskData?.tasks || []
  const triggers = triggerData?.triggers || []

  const sensorTask = tasks.find(t => t.name === 'SENSOR_GENERATION_TASK')
  const cleanupTask = tasks.find(t => t.name === 'SENSOR_CLEANUP_TASK')
  const simulationActive = sensorTask?.state === 'started'

  const activeTrigger = triggers.find(t => t.trigger_active)

  const toggleSimulation = async (enable: boolean) => {
    setIsToggling(true)
    try {
      const response = await fetch(`${API_BASE}/api/toggle-simulation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enable }),
      })
      if (response.ok) {
        await mutateTasks()
      }
    } catch (error) {
      console.error('Failed to toggle simulation:', error)
    } finally {
      setIsToggling(false)
    }
  }

  const injectAnomaly = async (assetId: string | null) => {
    setIsInjecting(true)
    try {
      const response = await fetch(`${API_BASE}/api/inject-anomaly`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset_id: assetId }),
      })
      if (response.ok) {
        await mutateTriggers()
      }
    } catch (error) {
      console.error('Failed to inject anomaly:', error)
    } finally {
      setIsInjecting(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-200">Simulation Controls</h1>
        <p className="text-slate-400 text-sm mt-1">Manage background tasks and anomaly injection</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-navy-800/50 rounded-xl border border-navy-700/50 overflow-hidden">
          <div className="px-5 py-4 border-b border-navy-700/50">
            <div className="flex items-center gap-3">
              <Activity size={20} className="text-accent-blue" />
              <h2 className="text-lg font-semibold text-slate-200">Live Sensor Simulation</h2>
            </div>
          </div>
          <div className="p-5 space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-300">Sensor Generation Task</p>
                <p className="text-xs text-slate-500 mt-0.5">Generates simulated sensor readings</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                  simulationActive 
                    ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                    : 'bg-slate-600/20 text-slate-400 border border-slate-600/30'
                }`}>
                  {simulationActive ? 'Running' : 'Stopped'}
                </span>
              </div>
            </div>

            {sensorTask && (
              <div className="bg-navy-900/50 rounded-lg p-3 space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Schedule</span>
                  <span className="text-slate-300 font-mono">{sensorTask.schedule || 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Warehouse</span>
                  <span className="text-slate-300 font-mono">{sensorTask.warehouse || 'N/A'}</span>
                </div>
                {sensorTask.last_run && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Last Run</span>
                    <span className="text-slate-300">{new Date(sensorTask.last_run).toLocaleString()}</span>
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={() => toggleSimulation(true)}
                disabled={isToggling || simulationActive}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  simulationActive
                    ? 'bg-navy-700/50 text-slate-500 cursor-not-allowed'
                    : 'bg-green-500/20 text-green-400 hover:bg-green-500/30 border border-green-500/30'
                }`}
              >
                {isToggling && !simulationActive ? (
                  <RefreshCw size={16} className="animate-spin" />
                ) : (
                  <Play size={16} />
                )}
                Resume
              </button>
              <button
                onClick={() => toggleSimulation(false)}
                disabled={isToggling || !simulationActive}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  !simulationActive
                    ? 'bg-navy-700/50 text-slate-500 cursor-not-allowed'
                    : 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 border border-amber-500/30'
                }`}
              >
                {isToggling && simulationActive ? (
                  <RefreshCw size={16} className="animate-spin" />
                ) : (
                  <Pause size={16} />
                )}
                Suspend
              </button>
            </div>

            {cleanupTask && (
              <div className="pt-3 border-t border-navy-700/30">
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <Trash2 size={14} className="text-slate-500" />
                    <span className="text-slate-400">Cleanup Task</span>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    cleanupTask.state === 'started'
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-slate-600/20 text-slate-400'
                  }`}>
                    {cleanupTask.state === 'started' ? 'Running' : 'Stopped'}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="bg-navy-800/50 rounded-xl border border-navy-700/50 overflow-hidden">
          <div className="px-5 py-4 border-b border-navy-700/50">
            <div className="flex items-center gap-3">
              <Zap size={20} className="text-amber-400" />
              <h2 className="text-lg font-semibold text-slate-200">Anomaly Injection</h2>
            </div>
          </div>
          <div className="p-5 space-y-5">
            {!simulationActive ? (
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4 flex items-start gap-3">
                <AlertTriangle size={18} className="text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text-amber-300 font-medium">Simulation Not Running</p>
                  <p className="text-xs text-amber-400/70 mt-1">
                    Start the sensor simulation to enable anomaly injection
                  </p>
                </div>
              </div>
            ) : (
              <>
                <div>
                  <p className="text-sm text-slate-300 mb-3">Select asset for anomaly injection</p>
                  <div className="grid grid-cols-2 gap-2">
                    {SIMULATION_ASSETS.map(asset => {
                      const isActive = activeTrigger?.asset_id === asset
                      return (
                        <button
                          key={asset}
                          onClick={() => injectAnomaly(isActive ? null : asset)}
                          disabled={isInjecting}
                          className={`px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                            isActive
                              ? 'bg-red-500/20 text-red-400 border-2 border-red-500/50 shadow-lg shadow-red-500/10'
                              : 'bg-navy-700/50 text-slate-300 border border-navy-600 hover:border-accent-blue/50 hover:bg-navy-700'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span>{asset}</span>
                            {isActive && <Zap size={14} className="text-red-400" />}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {activeTrigger && (
                  <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Zap size={16} className="text-red-400" />
                      <span className="text-sm font-medium text-red-300">Active Anomaly</span>
                    </div>
                    <div className="space-y-1 text-xs">
                      <div className="flex justify-between">
                        <span className="text-red-400/70">Asset</span>
                        <span className="text-red-300 font-mono">{activeTrigger.asset_id}</span>
                      </div>
                      {activeTrigger.triggered_at && (
                        <div className="flex justify-between">
                          <span className="text-red-400/70">Triggered At</span>
                          <span className="text-red-300">{new Date(activeTrigger.triggered_at).toLocaleString()}</span>
                        </div>
                      )}
                      {activeTrigger.triggered_by && (
                        <div className="flex justify-between">
                          <span className="text-red-400/70">Triggered By</span>
                          <span className="text-red-300">{activeTrigger.triggered_by}</span>
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => injectAnomaly(null)}
                      disabled={isInjecting}
                      className="w-full mt-3 px-3 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded-lg text-xs font-medium transition-colors"
                    >
                      {isInjecting ? (
                        <RefreshCw size={14} className="animate-spin mx-auto" />
                      ) : (
                        'Clear Anomaly'
                      )}
                    </button>
                  </div>
                )}

                {!activeTrigger && (
                  <div className="bg-navy-900/50 rounded-lg p-4 text-center">
                    <Clock size={24} className="mx-auto text-slate-600 mb-2" />
                    <p className="text-sm text-slate-400">No active anomaly injection</p>
                    <p className="text-xs text-slate-500 mt-1">Select an asset above to inject an anomaly</p>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      <div className="bg-navy-800/50 rounded-xl border border-navy-700/50 overflow-hidden">
        <div className="px-5 py-4 border-b border-navy-700/50">
          <h2 className="text-lg font-semibold text-slate-200">All Background Tasks</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-slate-500 uppercase tracking-wider">
                <th className="px-5 py-3 font-medium">Task Name</th>
                <th className="px-5 py-3 font-medium">State</th>
                <th className="px-5 py-3 font-medium">Schedule</th>
                <th className="px-5 py-3 font-medium">Warehouse</th>
                <th className="px-5 py-3 font-medium">Last Run</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-700/30">
              {tasks.length > 0 ? (
                tasks.map((task, idx) => (
                  <tr key={idx} className="text-sm">
                    <td className="px-5 py-3">
                      <span className="font-mono text-slate-300">{task.name}</span>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        task.state === 'started'
                          ? 'bg-green-500/20 text-green-400'
                          : task.state === 'suspended'
                          ? 'bg-amber-500/20 text-amber-400'
                          : 'bg-slate-600/20 text-slate-400'
                      }`}>
                        {task.state}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-400 font-mono text-xs">{task.schedule || '-'}</td>
                    <td className="px-5 py-3 text-slate-400 font-mono text-xs">{task.warehouse || '-'}</td>
                    <td className="px-5 py-3 text-slate-400 text-xs">
                      {task.last_run ? new Date(task.last_run).toLocaleString() : '-'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-slate-500">
                    No tasks found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
