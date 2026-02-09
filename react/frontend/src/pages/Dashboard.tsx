import useSWR from 'swr'
import { MetricCard } from '../components/MetricCard'
import { AssetTile, type Asset } from '../components/AssetTile'
import { PriorityTable } from '../components/PriorityTable'
import { AlertTriangle, Clock, DollarSign, TrendingUp } from 'lucide-react'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

function DashboardSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      <div className="h-8 w-64 bg-navy-700 rounded" />
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-24 bg-navy-800 rounded-xl" />
        ))}
      </div>
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-48 bg-navy-800 rounded-xl" />
        ))}
      </div>
      <div className="h-64 bg-navy-800 rounded-xl" />
    </div>
  )
}

export function Dashboard() {
  const { data, error, isLoading } = useSWR<{ decisions: Asset[] }>('/api/decisions', fetcher)

  if (isLoading) return <DashboardSkeleton />
  if (error) {
    return (
      <div className="p-6">
        <div className="card border-accent-red/50 bg-accent-red/5">
          <h2 className="text-accent-red font-semibold mb-2">Error Loading Data</h2>
          <p className="text-slate-400 text-sm">Failed to fetch maintenance decisions from API.</p>
          <button onClick={() => window.location.reload()} className="btn-primary mt-4">
            Retry
          </button>
        </div>
      </div>
    )
  }

  const decisions = data?.decisions || []
  const urgentCount = decisions.filter((d) => d.RECOMMENDATION === 'URGENT').length
  const planPMCount = decisions.filter((d) => d.RECOMMENDATION === 'PLAN_PM').length
  const totalExpectedLoss = decisions.reduce((sum, d) => sum + d.EXPECTED_UNPLANNED_COST, 0)
  const totalNetBenefit = decisions
    .filter((d) => d.NET_BENEFIT > 0)
    .reduce((sum, d) => sum + d.NET_BENEFIT, 0)

  const topAssets = decisions.filter((d) => d.NET_BENEFIT > 0).slice(0, 3)

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Asset Risk & Maintenance Priorities</h1>
        <p className="text-slate-400 mt-1">Expected-cost decision framework for predictive maintenance</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Urgent PM Required"
          value={urgentCount}
          subtitle="Assets with P(fail) × Cost > PM Cost"
          icon={<AlertTriangle size={20} className="text-accent-red" />}
          variant="urgent"
        />
        <MetricCard
          title="Plan PM"
          value={planPMCount}
          subtitle="Schedule within target window"
          icon={<Clock size={20} className="text-accent-yellow" />}
          variant="warning"
        />
        <MetricCard
          title="Total Expected Loss"
          value={`$${totalExpectedLoss.toLocaleString()}`}
          subtitle="Sum of E[unplanned cost]"
          icon={<DollarSign size={20} className="text-accent-blue" />}
        />
        <MetricCard
          title="Net Savings (PM)"
          value={`$${totalNetBenefit.toLocaleString()}`}
          subtitle="If all PM recommendations followed"
          icon={<TrendingUp size={20} className="text-accent-green" />}
          variant="success"
        />
      </div>

      <div>
        <h2 className="text-lg font-semibold text-slate-200 mb-4">Top Priority Assets</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {topAssets.map((asset) => (
            <AssetTile key={asset.ASSET_ID} asset={asset} />
          ))}
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-slate-200 mb-4">Maintenance Priority Queue</h2>
        <p className="text-sm text-slate-400 mb-4">Sorted by net benefit of intervention</p>
        <PriorityTable assets={decisions} />
      </div>
    </div>
  )
}
