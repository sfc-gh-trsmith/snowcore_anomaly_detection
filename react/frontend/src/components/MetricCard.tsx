import { memo } from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface MetricCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon?: React.ReactNode
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  variant?: 'default' | 'urgent' | 'warning' | 'success'
}

export const MetricCard = memo(function MetricCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  trendValue,
  variant = 'default',
}: MetricCardProps) {
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus
  const trendColor =
    trend === 'up' ? 'text-accent-green' : trend === 'down' ? 'text-accent-red' : 'text-slate-400'

  const variantStyles = {
    default: 'border-navy-700/50',
    urgent: 'border-accent-red/50 bg-accent-red/5',
    warning: 'border-accent-yellow/50 bg-accent-yellow/5',
    success: 'border-accent-green/50 bg-accent-green/5',
  }

  const valueColors = {
    default: 'text-accent-blue',
    urgent: 'text-accent-red',
    warning: 'text-accent-yellow',
    success: 'text-accent-green',
  }

  return (
    <article className={`card card-glow ${variantStyles[variant]}`}>
      <div className="flex items-center gap-3">
        {icon && (
          <div
            className="w-10 h-10 rounded-xl bg-accent-blue/20 flex items-center justify-center"
            aria-hidden="true"
          >
            {icon}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-400 truncate">{title}</p>
          <p className={`text-2xl font-semibold tabular-nums ${valueColors[variant]}`}>{value}</p>
          {subtitle && <p className="text-xs text-slate-500 truncate">{subtitle}</p>}
        </div>
        {trend && (
          <div className={`flex items-center gap-1 ${trendColor}`} aria-label={`Trend: ${trend}`}>
            <TrendIcon size={16} aria-hidden="true" />
            {trendValue && <span className="text-sm tabular-nums">{trendValue}</span>}
          </div>
        )}
      </div>
    </article>
  )
})
