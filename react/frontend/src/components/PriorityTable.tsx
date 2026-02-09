import { memo } from 'react'
import type { Asset } from './AssetTile'

interface PriorityTableProps {
  assets: Asset[]
  onRowClick?: (asset: Asset) => void
}

export const PriorityTable = memo(function PriorityTable({ assets, onRowClick }: PriorityTableProps) {
  return (
    <div className="card overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-navy-700/50 bg-navy-800/50">
              <th className="text-left p-4 text-slate-400 font-medium">Asset</th>
              <th className="text-right p-4 text-slate-400 font-medium">Risk (7d)</th>
              <th className="text-right p-4 text-slate-400 font-medium">Expected Loss</th>
              <th className="text-right p-4 text-slate-400 font-medium">PM Cost</th>
              <th className="text-right p-4 text-slate-400 font-medium">Net Benefit</th>
              <th className="text-center p-4 text-slate-400 font-medium">Action</th>
              <th className="text-center p-4 text-slate-400 font-medium">Window</th>
            </tr>
          </thead>
          <tbody>
            {assets.map((asset, idx) => {
              const isUrgent = asset.RECOMMENDATION === 'URGENT'
              const isPlanPM = asset.RECOMMENDATION === 'PLAN_PM'
              return (
                <tr
                  key={asset.ASSET_ID}
                  onClick={() => onRowClick?.(asset)}
                  className={`border-b border-navy-700/30 hover:bg-navy-700/30 cursor-pointer transition-colors ${
                    idx % 2 === 0 ? 'bg-navy-800/20' : ''
                  }`}
                >
                  <td className="p-4 font-medium text-slate-200">{asset.ASSET_ID}</td>
                  <td className="p-4 text-right tabular-nums">
                    <span
                      className={
                        asset.P_FAIL_7D > 0.3
                          ? 'text-accent-red'
                          : asset.P_FAIL_7D > 0.15
                            ? 'text-accent-yellow'
                            : 'text-slate-300'
                      }
                    >
                      {Math.round(asset.P_FAIL_7D * 100)}%
                    </span>
                  </td>
                  <td className="p-4 text-right tabular-nums text-slate-300">
                    ${asset.EXPECTED_UNPLANNED_COST.toLocaleString()}
                  </td>
                  <td className="p-4 text-right tabular-nums text-slate-400">
                    ${asset.C_PM_USD.toLocaleString()}
                  </td>
                  <td className="p-4 text-right tabular-nums">
                    <span className={asset.NET_BENEFIT > 0 ? 'text-accent-green' : 'text-slate-400'}>
                      ${asset.NET_BENEFIT.toLocaleString()}
                    </span>
                  </td>
                  <td className="p-4 text-center">
                    <span
                      className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                        isUrgent
                          ? 'bg-accent-red/20 text-accent-red'
                          : isPlanPM
                            ? 'bg-accent-yellow/20 text-accent-yellow'
                            : 'bg-accent-green/20 text-accent-green'
                      }`}
                    >
                      {asset.RECOMMENDATION.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="p-4 text-center text-slate-400">{asset.TARGET_WINDOW}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
})
