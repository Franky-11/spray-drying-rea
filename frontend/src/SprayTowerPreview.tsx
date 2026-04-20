import type { CompareScenarioResponse } from './apiTypes'

interface SprayTowerPreviewProps {
  scenario: CompareScenarioResponse
  hoveredHeightM: number | null
}

function SprayTowerPreview({ scenario, hoveredHeightM }: SprayTowerPreviewProps) {
  const cylinderHeight = scenario.inputs.cylinder_height_m ?? scenario.profile.dryer_exit_h_m
  const coneHeight = scenario.inputs.cone_height_m
  const outletDuctLength = scenario.inputs.outlet_duct_length_m
  const dryerDiameter = scenario.inputs.dryer_diameter_m
  const outletDuctDiameter = scenario.inputs.outlet_duct_diameter_m ?? scenario.inputs.dryer_diameter_m * 0.2
  const totalHeightM = Math.max(scenario.profile.axial_length_m, cylinderHeight + coneHeight + outletDuctLength, 1e-6)
  const clampedHeight = hoveredHeightM === null ? null : clamp(hoveredHeightM, 0, totalHeightM)
  const activePoint = clampedHeight === null ? null : findClosestPoint(scenario, clampedHeight)

  const viewBoxWidth = 240
  const viewBoxHeight = 420
  const topY = 28
  const bottomY = 318
  const ductEndX = 214
  const centerX = 100
  const verticalScale = (bottomY - topY) / Math.max(cylinderHeight + coneHeight, 1e-6)
  const horizontalScale = (ductEndX - centerX) / Math.max(outletDuctLength, 1e-6)
  const cylinderBottomY = topY + cylinderHeight * verticalScale
  const coneBottomY = cylinderBottomY + coneHeight * verticalScale
  const maxDiameter = Math.max(dryerDiameter, outletDuctDiameter, 1e-6)
  const cylinderHalfWidth = 44
  const outletHalfWidth = Math.max(10, (outletDuctDiameter / maxDiameter) * cylinderHalfWidth)
  const coneBottomHalfWidth = Math.max(outletHalfWidth + 6, outletHalfWidth * 1.35)
  const outletTopY = coneBottomY - outletHalfWidth
  const outletBottomY = coneBottomY + outletHalfWidth
  const outlinePath = [
    `M ${centerX - cylinderHalfWidth} ${topY}`,
    `L ${centerX - cylinderHalfWidth} ${cylinderBottomY}`,
    `L ${centerX - coneBottomHalfWidth} ${coneBottomY}`,
    `L ${centerX} ${coneBottomY}`,
    `L ${centerX} ${outletTopY}`,
    `L ${ductEndX} ${outletTopY}`,
    `L ${ductEndX} ${outletBottomY}`,
    `L ${centerX} ${outletBottomY}`,
    `L ${centerX} ${coneBottomY}`,
    `L ${centerX + coneBottomHalfWidth} ${coneBottomY}`,
    `L ${centerX + cylinderHalfWidth} ${cylinderBottomY}`,
    `L ${centerX + cylinderHalfWidth} ${topY}`,
    'Z',
  ].join(' ')
  const centerlinePath = [
    `M ${centerX} ${topY}`,
    `L ${centerX} ${coneBottomY}`,
    `L ${ductEndX} ${coneBottomY}`,
  ].join(' ')

  const progressPoint = clampedHeight === null
    ? null
    : projectHeightToTowerPoint(clampedHeight, {
        centerX,
        topY,
        cylinderHeight,
        coneHeight,
        outletDuctLength,
        verticalScale,
        horizontalScale,
        coneBottomY,
      })

  const progressPath =
    progressPoint === null || clampedHeight === null
      ? null
      : [
          `M ${centerX} ${topY}`,
          clampedHeight <= cylinderHeight + coneHeight
            ? `L ${progressPoint.x} ${progressPoint.y}`
            : `L ${centerX} ${coneBottomY} L ${progressPoint.x} ${progressPoint.y}`,
        ].join(' ')

  return (
    <aside className="tower-panel" aria-label="Spruehturm-Vorschau">
      <div className="tower-panel-header">
        <h3 className="panel-title">Turmposition</h3>
        <span className="tower-scenario-label">{scenario.label}</span>
      </div>
      <div className="tower-panel-body">
        <svg className="tower-svg" viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`} role="img">
          <path className="tower-outline" d={outlinePath} />
          <path className="tower-body" d={outlinePath} />
          <path className="tower-centerline" d={centerlinePath} />
          {progressPath && <path className="tower-progress" d={progressPath} />}
          {progressPoint && <circle className="tower-marker" cx={progressPoint.x} cy={progressPoint.y} r="6" />}
          <text className="tower-label" x={centerX + cylinderHalfWidth + 16} y={topY + 16}>
            Zylinder
          </text>
          <text className="tower-label" x={centerX + cylinderHalfWidth + 16} y={cylinderBottomY + 8}>
            Konus
          </text>
          <text className="tower-label" x={centerX + 30} y={coneBottomY - outletHalfWidth - 10}>
            Abluftrohr
          </text>
        </svg>
        <div className="tower-stats">
          <div className="tower-stat">
            <span className="label">Aktuelle Hoehe</span>
            <strong>{clampedHeight === null ? 'Plot hovern' : `${formatValue(clampedHeight)} m`}</strong>
          </div>
          <div className="tower-stat">
            <span className="label">Abschnitt</span>
            <strong>{activePoint?.section ?? 'n/a'}</strong>
          </div>
          <div className="tower-stat">
            <span className="label">Turmlaenge</span>
            <strong>{formatValue(totalHeightM)} m</strong>
          </div>
          <div className="tower-stat">
            <span className="label">Geometrie</span>
            <strong>
              {formatValue(cylinderHeight)} / {formatValue(coneHeight)} / {formatValue(outletDuctLength)} m
            </strong>
          </div>
        </div>
      </div>
    </aside>
  )
}

function projectHeightToTowerPoint(
  height: number,
  geometry: {
    centerX: number
    topY: number
    cylinderHeight: number
    coneHeight: number
    outletDuctLength: number
    verticalScale: number
    horizontalScale: number
    coneBottomY: number
  },
) {
  const { centerX, topY, cylinderHeight, coneHeight, outletDuctLength, verticalScale, horizontalScale, coneBottomY } =
    geometry
  if (height <= cylinderHeight + coneHeight) {
    return {
      x: centerX,
      y: topY + height * verticalScale,
    }
  }

  const ductDistance = Math.min(height - cylinderHeight - coneHeight, outletDuctLength)
  return {
    x: centerX + ductDistance * horizontalScale,
    y: coneBottomY,
  }
}

function findClosestPoint(scenario: CompareScenarioResponse, hoveredHeightM: number) {
  let best = scenario.profile.series[0]
  let bestDistance = Math.abs(best.h_m - hoveredHeightM)
  for (const point of scenario.profile.series) {
    const distance = Math.abs(point.h_m - hoveredHeightM)
    if (distance < bestDistance) {
      best = point
      bestDistance = distance
    }
  }
  return best
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function formatValue(value: number): string {
  return value.toFixed(value >= 10 ? 1 : 2)
}

export default SprayTowerPreview
