import { memo } from 'react'
import { AlertTriangle, CheckCircle, Clock } from 'lucide-react'

export interface Asset {
  ASSET_ID: string
  P_FAIL_7D: number
  EXPECTED_UNPLANNED_COST: number
  C_PM_USD: number
  NET_BENEFIT: number
  RECOMMENDATION: string
  TARGET_WINDOW: string
  CONFIDENCE: number
}

interface AssetTileProps {
  asset: Asset
  onClick?: () => void
}

export const AssetTile = memo(function AssetTile({ asset, onClick }: AssetTileProps) {
  const isUrgent = asset.RECOMMENDATION === 'URGENT'
  const isPlanPM = asset.RECOMMENDATION === 'PLAN_PM'

  const StatusIcon = isUrgent ? AlertTriangle : isPlanPM ? Clock : CheckCircle
  const borderColor = isUrgent
    ? 'border-accent-red/50 hover:border-accent-red'
    : isPlanPM
      ? 'border-accent-yellow/50 hover:border-accent-yellow'
      : 'border-accent-green/50 hover:border-accent-green'
  const bgColor = isUrgent
    ? 'bg-accent-red/5'
    : isPlanPM
      ? 'bg-accent-yellow/5'
      : 'bg-accent-green/5'
  const iconColor = isUrgent
    ? 'text-accent-red'
    : isPlanPM
      ? 'text-accent-yellow'
      : 'text-accent-green'

  return (
    <button
      onClick={onClick}
      className={`card ${bgColor} ${borderColor} text-left transition-all hover:scale-[1.02] focus-visible:ring-2 focus-visible:ring-accent-blue`}
      aria-label={`${asset.ASSET_ID}: ${asset.RECOMMENDATION} - ${Math.round(asset.P_FAIL_7D * 100)}% risk`}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-slate-200">{asset.ASSET_ID}</h3>
          <span
            className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
              isUrgent
                ? 'bg-accent-red/20 text-accent-red'
                : isPlanPM
                  ? 'bg-accent-yellow/20 text-accent-yellow'
                  : 'bg-accent-green/20 text-accent-green'
            }`}
          >
            <StatusIcon size={12} />
            {asset.RECOMMENDATION.replace('_', ' ')}
          </span>
        </div>
        <div className={`text-2xl font-bold ${iconColor}`}>{Math.round(asset.P_FAIL_7D * 100)}%</div>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-400">Expected Loss</span>
          <span className="text-slate-200 font-medium">${asset.EXPECTED_UNPLANNED_COST.toLocaleString()}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">PM Cost</span>
          <span className="text-slate-200">${asset.C_PM_USD.toLocaleString()}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Net Benefit</span>
          <span className={asset.NET_BENEFIT > 0 ? 'text-accent-green font-medium' : 'text-slate-400'}>
            ${asset.NET_BENEFIT.toLocaleString()}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Window</span>
          <span className="text-slate-200">{asset.TARGET_WINDOW}</span>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-navy-700/50">
        <div className="flex justify-between text-xs">
          <span className="text-slate-500">Confidence</span>
          <span className="text-slate-400">{Math.round(asset.CONFIDENCE * 100)}%</span>
        </div>
        <div className="mt-1 h-1.5 bg-navy-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-accent-blue rounded-full transition-all"
            style={{ width: `${asset.CONFIDENCE * 100}%` }}
          />
        </div>
      </div>
    </button>
  )
})
