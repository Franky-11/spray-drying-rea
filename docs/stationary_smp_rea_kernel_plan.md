# Stationary SMP REA Kernel: Target Structure Plan

## Objective

Define the target structure of a clean stationary SMP REA kernel before implementation.

This document answers:

- which coordinate the kernel should use
- which state vector it should solve
- which quantities are differential vs algebraic
- how `Qloss` and humid-air enthalpy should be handled
- how the SMP REA material closure should be embedded
- how the new code should be split into files

## Main recommendation

Build the new stationary kernel as a height-based 1D parallel-flow solver.

Recommended independent variable:

```math
h \in [0, L]
```

Reason:

- `h` is the native coordinate of the Langrish design equations.
- It keeps geometry, co-current coupling, and distributed heat loss in the model itself instead of as post-processing.
- It allows residence time to be derived from velocity rather than guessed first.
- It removes the current mathematical shortcut where a lumped time trajectory is only re-labeled as height afterwards.

## Target state vector

Recommended baseline state vector:

```math
\mathbf z(h) =
\begin{bmatrix}
X \\
T_p \\
Y \\
H_h \\
U_p \\
\tau
\end{bmatrix}
```

with:

- `X`: particle moisture content on dry basis, kg water / kg dry solids
- `T_p`: particle temperature, K
- `Y`: bulk-air humidity on dry-air basis, kg water / kg dry air
- `H_h`: humid-air enthalpy per kg dry air, J / kg dry air
- `U_p`: representative axial particle velocity, m / s
- `tau`: optional residence-time diagnostic, s

The optional diagnostic state is:

```math
\frac{d\tau}{dh} = \frac{1}{U_p}
```

If the implementation wants the smallest possible first version, `tau` can be computed afterwards by quadrature instead of being part of the state vector.

## Differential equations

### 1. Moisture

```math
\frac{dX}{dh}
=
- \frac{h_m A_p}{m_s U_p}\left(\rho_{v,s} - \rho_{v,a}\right)
```

### 2. Particle temperature

```math
\frac{dT_p}{dh}
=
\frac{\pi d_p k_a Nu (T_a - T_p) + \frac{dm_p}{dh} U_p H_{fg}}
{m_s (C_{ps} + X C_{pw}) U_p}
```

### 3. Air humidity

```math
\frac{dY}{dh}
=
- \frac{\dot m_s}{\dot m_{da}} \frac{dX}{dh}
```

### 4. Air enthalpy

```math
\frac{dH_h}{dh}
=
- \frac{\dot m_s}{\dot m_{da}} (C_{ps} + X C_{pw}) \frac{dT_p}{dh}
- \frac{UA}{L \dot m_{da}} (T_a - T_{amb})
```

### 5. Particle velocity

```math
\frac{dU_p}{dh}
=
\left[
\left(1 - \frac{\rho_a}{\rho_p}\right) g
- \frac{3}{4}\frac{\rho_a C_D U_R (U_p - U_a)}{\rho_p d_p}
\right]\frac{1}{U_p}
```

with:

```math
U_R = |U_p - U_a|
```

### 6. Optional residence-time state

```math
\frac{d\tau}{dh} = \frac{1}{U_p}
```

## Algebraic closure set

These quantities should be closed algebraically at each `h`.

### Gas thermodynamics

```math
H_h = C_{pa}(T_a - T_{ref}) + Y[\lambda + C_{pv}(T_a - T_{ref})]
```

Invert this relation to obtain `T_a`.

Then compute:

- `p_sat(T_a)`
- `p_v(Y)`
- `RH_a = p_v / p_sat(T_a)`
- `rho_v,a`
- `rho_a`
- `mu_a`
- `k_a`
- `D_v`
- `U_a = \dot m_{ha} / (\rho_a A_chamber)` from continuity with constant chamber cross-section

### SMP equilibrium moisture

Default baseline closure:

```math
X_b = X_eq(T_a, RH_a)
```

Use the skim-milk sorption relation from `Langrish` as the baseline algebraic closure for `X_b`:

```math
X_b(h) =
0.1499 \exp\left[-2.306 \times 10^{-3} T_{a,K}(h)\right]
\left[\ln\left(\frac{1}{RH_a(h)}\right)\right]^{0.4}
```

Equivalent form if air temperature is carried in degree Celsius:

```math
X_b(h) =
0.1499 \exp\left[-2.306 \times 10^{-3} (T_{a,^\circ C}(h) + 273.15)\right]
\left[\ln\left(\frac{1}{RH_a(h)}\right)\right]^{0.4}
```

Important:

- `X_b` is a closure input to the Chew REA curve.
- It should not be hardcoded inside the REA material function itself.
- If a better SMP-specific dryer-condition isotherm is added later, it should replace only this closure module, not the kernel balances.

Optional sensitivity-test branch:

- keep the legacy temperature-dependent GAB closure as a second candidate
- source: `references/Lin_eq_gab.md` from Lin, Chen, Pearce (2005)
- the coefficient set matches the currently implemented formula in `core/model.py`

Working candidate formula from the legacy kernel:

```math
X_b =
\frac{C(T) K(T) m_0 RH}
{(1-K(T)RH)(1-K(T)RH + C(T)K(T)RH)}
```

with

```math
m_0 = 0.06156
\qquad
C(T) = 0.001645 \exp\left(\frac{24831}{RT}\right)
\qquad
K(T) = 5.710 \exp\left(-\frac{5118}{RT}\right)
```

This optional GAB branch is now reference-backed in the repo and is intended for comparison runs against the Langrish baseline, not yet as the default production closure.

### SMP REA material function

Use the Chew piecewise high-solids SMP function:

1. define `delta = X - X_b`
2. evaluate the Chew critical point for the chosen initial solids
3. use the early-stage linear branch above the critical point
4. use the common polynomial branch below the critical point
5. compute

```math
\Delta E_v = f_{SMP}(delta; X_0)\,\Delta E_{v,max}
```

and

```math
\psi = \exp\left(-\frac{\Delta E_v}{R T_p}\right)
```

This means the solver must reevaluate at every axial RHS evaluation:

```math
X_b(h) \rightarrow \delta(h)=X(h)-X_b(h) \rightarrow \frac{\Delta E_v}{\Delta E_{v,max}} \rightarrow \Delta E_v \rightarrow \psi(h)
```

Recommended citation envelope for this closure:

- REA curve interpolation: 30-43 wt from Chew Table 2 and Table 3
- do not silently extend the Chew REA law to 50 wt unless that specific source is added to the baseline

### Surface vapor density

```math
\rho_{v,s} = \psi \rho_{v,sat}(T_p)
```

### SMP shrinkage

For SMP, use Chew linear shrinkage on the reduced moisture scale:

```math
\frac{d_p}{d_{p,0}} = g_{SMP}(X - X_b; X_0)
```

Recommended citation envelope for this closure:

- exact tabulated shrinkage anchors: 37, 40, and 43 wt from Chew Table 1
- interpolation inside that anchor range is acceptable
- extrapolation outside that anchor range should not be silent

Then derive particle density from mass and volume:

```math
m_p = m_s (1 + X)
```

```math
\rho_p = \frac{6 m_p}{\pi d_p^3}
```

This is cleaner for SMP than combining an empirical diameter law with a separate balloon-density law.

### Transport closure

Use:

- `Re`
- `Sc`
- `Sh`
- `Pr`
- `Nu`
- `C_D`

from the Langrish / Ranz-Marshall closure set.

Then define:

```math
h_m = \frac{Sh D_v}{d_p}
```

```math
h_h = \frac{Nu k_a}{d_p}
```

## Why `H_h` should be a state and `T_a` should be algebraic

This is a key design decision.

Recommended:

- state: `H_h`
- algebraic output: `T_a`

Reason:

1. The Langrish gas-side balance is written in terms of humid-air enthalpy.
2. When `Y` changes, the effective heat capacity of the air side changes with it.
3. A direct `dT_a/dh` formulation easily hides or duplicates latent terms.
4. The enthalpy state keeps the gas-side energy bookkeeping explicit and source-aligned.

This is cleaner than the current legacy pattern, where an air-temperature ODE carries a mixed latent/sensible correction.

## How `Qloss` should be handled

Recommended treatment:

```math
Qloss'(h) = \frac{UA}{L}(T_a - T_{amb})
```

and place it directly in the air enthalpy balance.

This means:

- `Qloss` is distributed over height
- `Qloss` acts on the chamber / gas-side energy balance
- `Qloss` is not a separate outlet correction
- `Qloss` is not attached to the representative particle balance

## Dynamic vs algebraic quantities

Recommended differential quantities:

- `X`
- `T_p`
- `Y`
- `H_h`
- `U_p`
- optional `tau`

Recommended algebraic quantities:

- `T_a`
- `RH_a`
- `p_v`
- `p_sat(T_a)`
- `rho_v,a`
- `rho_v,sat(T_a)`
- `rho_v,sat(T_p)`
- `X_b`
- `DeltaE_v,max`
- `DeltaE_v`
- `psi`
- `d_p`
- `m_p`
- `rho_p`
- `U_a`
- `U_R`
- `Re`
- `Sc`
- `Sh`
- `Pr`
- `Nu`
- `C_D`
- `h_m`
- `h_h`
- `H_fg`

## Recommended validity policy

For the first implementation step, the kernel should be explicit about the citation envelope.

Recommended policy:

- baseline material support: SMP only
- baseline REA correlation support: only the Chew-supported high-solids regime
- REA interpolation envelope: 30-43 wt
- shrinkage anchor envelope: 37-43 wt
- no baseline 50 wt support from the current reference set
- no silent extrapolation beyond the cited solids window
- out-of-range inputs should raise a model-validity warning or error

This is preferable to keeping a broader but poorly traceable parameter envelope.

## Recommended public interface

The new kernel should be implemented as a separate module, not as an extension of `core/model.py`.

Suggested top-level API:

```python
result = solve_stationary_smp_profile(inputs)
```

Where `inputs` contain:

- dryer geometry: `dryer_height_m`, `dryer_diameter_m`
- ambient / loss data: `ambient_temp_c`, `heat_loss_coeff_w_m2k`
- gas inlet: `inlet_air_temp_c`, `inlet_abs_humidity_g_kg`, `air_flow_m3_h`
- feed inlet: `feed_temp_c`, `feed_rate_kg_h`, `feed_total_solids`
- droplet descriptor: `droplet_size_um`, `initial_droplet_velocity_ms`
- material descriptor: `material="SMP"`

Suggested outputs:

- profile arrays over `h`
- outlet state
- residence time
- core diagnostics: `Re`, `Sh`, `Nu`, `psi`, `DeltaE_v`, `X_b`, `Qloss'`
- model-validity warnings
- reference provenance metadata

## Recommended file structure

Use a new package instead of patching `core/model.py`.

Suggested layout:

```text
core/
  stationary_smp_rea/
    __init__.py
    inputs.py
    kernel.py
    balances.py
    air.py
    transport.py
    particle.py
    materials/
      __init__.py
      smp_chew.py
```

Recommended responsibilities:

- `inputs.py`
  - input dataclasses
  - validation
  - derived inlet-flow quantities on dry bases

- `kernel.py`
  - public `solve_stationary_smp_profile()`
  - solver orchestration
  - result assembly

- `balances.py`
  - axial RHS for `dX/dh`, `dT_p/dh`, `dY/dh`, `dH_h/dh`, `dU_p/dh`
  - no material-specific coefficients hardcoded here

- `air.py`
  - moist-air enthalpy
  - enthalpy inversion to `T_a`
  - vapor pressure / humidity conversion
  - relative humidity
  - saturation and gas-property helpers

- `transport.py`
  - `Re`, `Sc`, `Sh`, `Pr`, `Nu`, `C_D`
  - `h_m`, `h_h`

- `particle.py`
  - representative droplet mass / geometry relations
  - density from `m_p` and `d_p`

- `materials/smp_chew.py`
  - Chew master activation curve
  - critical-point logic
  - Chew SMP shrinkage closure
  - validity bounds for the cited solids range

## What should explicitly not be migrated first

These items should stay out of the first clean implementation.

1. `core/model.py` legacy physics

Do not keep patching the current lumped kernel as the reference implementation.

2. WPC support

This chat is about a clean SMP baseline.

3. Process simulation layer

No dynamic plant wrapper before the stationary SMP kernel is correct.

4. Calibration knobs in the physics core

Do not carry over global transfer multipliers or equilibrium offsets into the new baseline module.

5. UI-shaped result metrics

First deliver the physical profile and outlet state; derived UI metrics can be layered later.

6. Multi-zone or radial model growth

No second zone, no radial bins, no deposition logic in the first clean step.

## Implementation sequence for the next chat

The next implementation step should proceed in this order:

1. create the new package skeleton
2. implement air-side dry-basis thermodynamics and enthalpy inversion
3. implement `materials/smp_chew.py`
4. implement both `X_b` closures behind one interface: Langrish baseline plus optional GAB candidate
5. implement transport closure from Langrish
6. implement the axial balance RHS
7. solve the profile over `h`
8. compare outlet and profile behavior for both `X_b` options
9. only then wire the new kernel into any app-facing layer

## Bottom line

The clean target is:

- coordinate: `h`
- core states: `X`, `T_p`, `Y`, `H_h`, `U_p`
- optional diagnostic state: `tau`
- Chew for SMP material closure
- Langrish for axial balances, transport, and `Qloss`
- separate new package under `core/`
- no further physics growth inside the current legacy lumped kernel
