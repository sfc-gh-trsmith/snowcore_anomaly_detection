import { useState, lazy, Suspense } from 'react'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { LayoutDashboard, MessageSquare, Network, BarChart3, Activity, Radio, Settings } from 'lucide-react'

const Analytics = lazy(() => import('./pages/Analytics'))
const GNNView = lazy(() => import('./pages/GNNView'))
const Chat = lazy(() => import('./pages/Chat'))
const Telemetry = lazy(() => import('./pages/Telemetry'))
const LiveSensors = lazy(() => import('./pages/LiveSensors'))
const TaskControls = lazy(() => import('./pages/TaskControls'))

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, description: 'Asset overview and priorities' },
  { id: 'telemetry', label: 'Telemetry', icon: Activity, description: 'Anomaly events and trends' },
  { id: 'live-sensors', label: 'Live Sensors', icon: Radio, description: 'Real-time sensor streaming by asset' },
  { id: 'analytics', label: 'Analytics', icon: BarChart3, description: 'Charts and efficient frontier' },
  { id: 'gnn', label: 'GNN Graph', icon: Network, description: 'Anomaly propagation network' },
  { id: 'chat', label: 'Copilot', icon: MessageSquare, description: 'AI-powered assistant' },
  { id: 'task-controls', label: 'Controls', icon: Settings, description: 'Simulation and task management' },
]

function PageSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      <div className="h-8 w-48 bg-navy-700 rounded" />
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-24 bg-navy-800 rounded-xl" />
        ))}
      </div>
      <div className="h-64 bg-navy-800 rounded-xl" />
    </div>
  )
}

export default function App() {
  const [currentPage, setCurrentPage] = useState('dashboard')

  return (
    <Layout
      currentPage={currentPage}
      onNavigate={setCurrentPage}
      navItems={navItems}
      appName="Snowcore Smart Manufacturing"
    >
      {currentPage === 'dashboard' && <Dashboard />}
      {currentPage === 'telemetry' && (
        <Suspense fallback={<PageSkeleton />}>
          <Telemetry />
        </Suspense>
      )}
      {currentPage === 'live-sensors' && (
        <Suspense fallback={<PageSkeleton />}>
          <LiveSensors />
        </Suspense>
      )}
      {currentPage === 'analytics' && (
        <Suspense fallback={<PageSkeleton />}>
          <Analytics />
        </Suspense>
      )}
      {currentPage === 'gnn' && (
        <Suspense fallback={<PageSkeleton />}>
          <GNNView />
        </Suspense>
      )}
      {currentPage === 'chat' && (
        <Suspense fallback={<PageSkeleton />}>
          <Chat />
        </Suspense>
      )}
      {currentPage === 'task-controls' && (
        <Suspense fallback={<PageSkeleton />}>
          <TaskControls />
        </Suspense>
      )}
    </Layout>
  )
}
