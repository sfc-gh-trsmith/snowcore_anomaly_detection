import { memo, useMemo } from 'react'
import useSWR from 'swr'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  Legend,
  ReferenceLine,
  ReferenceArea,
} from 'recharts'
import type { Asset } from '../components/AssetTile'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

const EfficientFrontier = memo(function EfficientFrontier({ assets }: { assets: Asset[] }) {
  const chartData = useMemo(() => {
    return assets.map((a) => ({
      name: a.ASSET_ID,
      pmCost: a.C_PM_USD,
      risk: a.P_FAIL_7D * 100,
      netBenefit: a.NET_BENEFIT,
      recommendation: a.RECOMMENDATION,
      size: Math.max(a.EXPECTED_UNPLANNED_COST / 2000, 8),
    }))
  }, [assets])

  const { slope, maxCost, maxRisk } = useMemo(() => {
    const positive = assets.filter((a) => a.NET_BENEFIT > 0)
    const maxCost = Math.max(...assets.map((a) => a.C_PM_USD), 60000)
    const maxRisk = Math.max(...assets.map((a) => a.P_FAIL_7D * 100), 35)
    
    if (positive.length === 0) {
      return { slope: maxRisk * 0.5 / maxCost, maxCost, maxRisk }
    }
    
    const avgRiskPerDollar = positive.reduce((s, a) => s + a.P_FAIL_7D * 100, 0) / 
                            positive.reduce((s, a) => s + a.C_PM_USD, 0)
    return { slope: avgRiskPerDollar, maxCost, maxRisk }
  }, [assets])

  const yDomainMax = Math.max(maxRisk, slope * maxCost) * 1.1

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-slate-200 mb-2">Maintenance Efficient Frontier</h3>
      <p className="text-sm text-slate-400 mb-4">
        Assets above the dashed line offer better risk reduction per dollar
      </p>
      <ResponsiveContainer width="100%" height={350}>
        <ScatterChart margin={{ top: 20, right: 20, bottom: 60, left: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="pmCost"
            type="number"
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
            stroke="#64748b"
            label={{ value: 'PM Cost ($)', position: 'bottom', offset: 40, fill: '#94a3b8' }}
            domain={[0, maxCost]}
          />
          <YAxis
            dataKey="risk"
            type="number"
            tickFormatter={(v) => `${v.toFixed(0)}%`}
            stroke="#64748b"
            label={{ value: 'Failure Risk (%)', angle: -90, position: 'left', offset: 40, fill: '#94a3b8' }}
            domain={[0, yDomainMax]}
          />
          <Tooltip
            cursor={{ strokeDasharray: '3 3' }}
            content={({ payload }) => {
              if (!payload?.[0]) return null
              const d = payload[0].payload
              return (
                <div className="bg-navy-800 border border-navy-700 rounded-lg p-3 shadow-xl">
                  <p className="font-semibold text-slate-200">{d.name}</p>
                  <p className="text-sm text-slate-400">PM Cost: ${d.pmCost.toLocaleString()}</p>
                  <p className="text-sm text-slate-400">Risk: {d.risk.toFixed(1)}%</p>
                  <p className={`text-sm ${d.netBenefit > 0 ? 'text-accent-green' : 'text-slate-400'}`}>
                    Net Benefit: ${d.netBenefit.toLocaleString()}
                  </p>
                </div>
              )
            }}
          />
          <ReferenceLine
            segment={[{ x: 0, y: 0 }, { x: maxCost, y: slope * maxCost }]}
            stroke="#666"
            strokeDasharray="5 5"
          />
          <Scatter 
            data={chartData}
            name="Assets"
            isAnimationActive={false}
          >
            {chartData.map((entry, i) => {
              const color = entry.recommendation === 'URGENT' ? '#ef4444' 
                : entry.recommendation === 'PLAN_PM' ? '#f59e0b' 
                : '#10b981'
              return <Cell key={i} fill={color} r={entry.size} />
            })}
          </Scatter>
          <Legend 
            verticalAlign="top" 
            height={36} 
            payload={[
              { value: 'Efficient Frontier', type: 'line', color: '#666' },
              { value: 'Urgent', type: 'circle', color: '#ef4444' },
              { value: 'Plan PM', type: 'circle', color: '#f59e0b' },
              { value: 'Monitor', type: 'circle', color: '#10b981' },
            ]}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
})

const SEVERITY_ORDER: Record<string, number> = {
  URGENT: 0,
  PLAN_PM: 1,
  MONITOR: 2,
}

const RECOMMENDATION_COLORS: Record<string, { unplanned: string; pm: string }> = {
  URGENT: { unplanned: '#ef4444', pm: '#fca5a5' },
  PLAN_PM: { unplanned: '#f59e0b', pm: '#fcd34d' },
  MONITOR: { unplanned: '#10b981', pm: '#6ee7b7' },
}

const CostComparison = memo(function CostComparison({ assets }: { assets: Asset[] }) {
  const data = useMemo(() => {
    return [...assets]
      .sort((a, b) => {
        const orderA = SEVERITY_ORDER[a.RECOMMENDATION] ?? 3
        const orderB = SEVERITY_ORDER[b.RECOMMENDATION] ?? 3
        if (orderA !== orderB) return orderA - orderB
        return b.NET_BENEFIT - a.NET_BENEFIT
      })
      .map((a) => ({
        name: a.ASSET_ID,
        unplannedCost: a.EXPECTED_UNPLANNED_COST,
        pmCost: a.C_PM_USD,
        netBenefit: a.NET_BENEFIT,
        recommendation: a.RECOMMENDATION,
      }))
  }, [assets])

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-slate-200 mb-2">Cost Comparison by Asset</h3>
      <p className="text-sm text-slate-400 mb-4">Expected unplanned cost vs PM cost per asset (ordered by severity)</p>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data} margin={{ top: 20, right: 20, bottom: 80, left: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis 
            dataKey="name" 
            stroke="#64748b" 
            angle={-45} 
            textAnchor="end" 
            height={80}
            interval={0}
            tick={{ fontSize: 11 }}
          />
          <YAxis 
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} 
            stroke="#64748b"
            label={{ value: 'Cost ($)', angle: -90, position: 'insideLeft', offset: -10, fill: '#94a3b8' }}
          />
          <Tooltip
            content={({ payload, label }) => {
              if (!payload?.length) return null
              const d = payload[0].payload
              return (
                <div className="bg-navy-800 border border-navy-700 rounded-lg p-3 shadow-xl">
                  <p className="font-semibold text-slate-200 mb-2">{label}</p>
                  <p className="text-sm text-red-400">
                    Unplanned: ${d.unplannedCost.toLocaleString()}
                  </p>
                  <p className="text-sm text-green-400">
                    PM Cost: ${d.pmCost.toLocaleString()}
                  </p>
                  <p className={`text-sm mt-1 pt-1 border-t border-navy-600 ${d.netBenefit > 0 ? 'text-accent-blue' : 'text-slate-400'}`}>
                    Net Benefit: ${d.netBenefit.toLocaleString()}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">{d.recommendation}</p>
                </div>
              )
            }}
          />
          <Legend verticalAlign="top" height={36} />
          <Bar 
            dataKey="unplannedCost" 
            name="Expected Unplanned Cost" 
            fill="#ef4444"
            radius={[4, 4, 0, 0]}
          />
          <Bar 
            dataKey="pmCost" 
            name="PM Cost" 
            fill="#10b981"
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
})

export default function Analytics() {
  const { data, isLoading } = useSWR<{ decisions: Asset[] }>('/api/decisions', fetcher)

  if (isLoading) {
    return (
      <div className="p-6 space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-navy-700 rounded" />
        <div className="h-96 bg-navy-800 rounded-xl" />
        <div className="h-64 bg-navy-800 rounded-xl" />
      </div>
    )
  }

  const decisions = data?.decisions || []

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Analytics</h1>
        <p className="text-slate-400 mt-1">Cost optimization and risk analysis</p>
      </div>

      <EfficientFrontier assets={decisions} />
      <CostComparison assets={decisions} />
    </div>
  )
}
