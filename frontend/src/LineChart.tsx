import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'

interface LineChartProps {
  option: echarts.EChartsOption
  onAxisValueChange?: (value: number | null) => void
}

interface AxisPointerEvent {
  axesInfo?: Array<{
    value?: number | string
  }>
}

function LineChart({ option, onAxisValueChange }: LineChartProps) {
  const elementRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!elementRef.current) {
      return
    }

    chartRef.current = echarts.init(elementRef.current, undefined, {
      renderer: 'canvas',
    })

    const resizeObserver = new ResizeObserver(() => {
      chartRef.current?.resize()
    })
    resizeObserver.observe(elementRef.current)

    return () => {
      resizeObserver.disconnect()
      chartRef.current?.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(option, true)
  }, [option])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !onAxisValueChange) {
      return
    }

    const handleAxisPointer = (event: unknown) => {
      const axisEvent = event as AxisPointerEvent
      const axisValue = axisEvent.axesInfo?.[0]?.value
      const numericValue = typeof axisValue === 'number' ? axisValue : Number(axisValue)
      onAxisValueChange(Number.isFinite(numericValue) ? numericValue : null)
    }

    const handleGlobalOut = () => {
      onAxisValueChange(null)
    }

    chart.on('updateAxisPointer', handleAxisPointer)
    chart.on('globalout', handleGlobalOut)

    return () => {
      chart.off('updateAxisPointer', handleAxisPointer)
      chart.off('globalout', handleGlobalOut)
    }
  }, [onAxisValueChange])

  return <div className="chart" ref={elementRef} />
}

export default LineChart
