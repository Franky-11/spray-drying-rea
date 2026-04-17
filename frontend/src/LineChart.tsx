import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'

interface LineChartProps {
  option: echarts.EChartsOption
}

function LineChart({ option }: LineChartProps) {
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

  return <div className="chart" ref={elementRef} />
}

export default LineChart
