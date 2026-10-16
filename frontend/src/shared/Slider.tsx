type SliderProps = {
  label: string
  value: number
  baselineValue: number
  balancePreview?: number
  onChange: (value: number) => void
  min?: number
  max?: number
}

export function Slider({ label, value, baselineValue, balancePreview = 0, onChange, min = 0, max = 100 }: SliderProps) {
  const range = max - min
  const currentPosition = range > 0 ? ((value - min) / range) * 100 : 0
  const damagePosition = range > 0 ? ((Math.max(value, baselineValue) - min) / range) * 100 : currentPosition
  const balancePosition = range > 0 ? Math.min(100, ((Math.max(value, baselineValue) + balancePreview - min) / range) * 100) : damagePosition

  return (
    <div className="grid grid-cols-[1fr_100px] items-center gap-4">
      <label className="font-medium">
        {label}
        <input
          aria-label={`${label}: ${value}%`}
          type="range"
          min={min}
          max={max}
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
          style={{ backgroundColor: 'rgb(255 255 255 / 0.14)', backgroundImage: `linear-gradient(to right, transparent 0%, transparent ${currentPosition}%, #f59e0b ${currentPosition}%, #f59e0b ${damagePosition}%, #22d3ee ${damagePosition}%, #22d3ee ${balancePosition}%, transparent ${balancePosition}%, transparent 100%), linear-gradient(to right, #6366f1 0%, #6366f1 ${currentPosition}%, transparent ${currentPosition}%, transparent 100%)`, backgroundSize: '100% 3px, 100% 8px', backgroundPosition: 'center', backgroundRepeat: 'no-repeat' }}
          className="allocation-slider mt-2 block h-2 w-full cursor-pointer appearance-none rounded-full"
        />
      </label>
      <label className="relative">
        <span className="sr-only">Percentual de {label}</span>
        <input
          type="number"
          min={min}
          max={max}
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
          className="w-full rounded-lg border border-(--slider-border) bg-transparent px-3 py-2 pr-8"
        />
        <span aria-hidden="true" className="absolute right-3 top-2 text-slate-500">%</span>
      </label>
    </div>
  )
}
