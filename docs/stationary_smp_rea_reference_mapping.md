# Stationary SMP REA Kernel: Reference Mapping

## Scope

This document fixes the reference baseline for a clean rebuild of the stationary SMP REA kernel.

Scope of this baseline:

- stationary kernel only
- SMP only
- co-current / parallel-flow 1D design form
- no WPC
- no process-control layer
- no UI refactor
- no further patching of the legacy lumped kernel in `core/model.py`

## Core decision

The new stationary kernel should be built on a height-based parallel-flow formulation `h`, not on the current lumped time form.

Reason:

- `Langrish (2009)` uses axial height `h` as the natural coordinate for the 1D co-current dryer design equations.
- Gas humidity, gas enthalpy, particle temperature, moisture, and particle velocity are all coupled along the dryer height in that framework.
- `Qloss` is naturally a distributed axial sink in that formulation.
- Time can still be recovered afterwards through `dt/dh = 1 / U_p`, but the reverse is not true for the current lumped time model.
- The current kernel uses a synthetic residence-time closure and a derived "display velocity" for transport closure, which is not a clean physical basis for `Re`, `Sh`, `Nu`, and `dm/dt`.

## Mapping table

| Topic | Adopted formulation | Primary source | Secondary / cross-check | Explicitly not adopted |
|---|---|---|---|---|
| Axial coordinate | Solve the stationary kernel in `h` from atomizer to outlet. | `references/Langrish (2009).md`, Sec. 3; `references/Langrish_parallel-flow design_eq.md`, Eqs. (20)-(42) | `references/foods.md`, Sec. 2.2 confirms REA + 1D coupling but uses `t` for dynamic control work. | Legacy time marching with post-hoc `height = progress * dryer_height`. |
| Particle moisture balance | Use Chew REA evaporation rate on a vapor-density basis, then convert to axial form: `dm_p/dh = (dm_p/dt) / U_p`. | `references/Chew_equations.md`, Eqs. (1), (6), (7) | `references/Langrish_parallel-flow design_eq.md`, Eq. (27) supports the axial `1/U_p` structure. | Langrish Eq. (27) pressure-based characteristic drying rate as the primary SMP drying law. |
| REA surface closure | `rho_v,s = psi * rho_v,sat(T_p)`, `psi = exp(-DeltaE_v / (R T_p))`. | `references/Chew_equations.md`, Eqs. (3)-(5) | `references/foods_equations.md`, Eq. (1) confirms the same REA pattern. | Any ad-hoc damping or ramp not tied to a cited REA correlation. |
| Equilibrium activation energy | `DeltaE_v,max = -R T_a ln(rho_v,a / rho_v,sat(T_a)) = -R T_a ln(RH_a)` with bulk-air equilibrium conditions. | `references/Chew_equations.md`, Eq. (10) | `references/foods_equations.md`, Eq. (4) is the same idea with slightly different notation. | Using the particle temperature directly inside `DeltaE_v,max` when evaluating the equilibrium reference state. |
| SMP master activation curve | Use the Chew piecewise SMP closure in normalized form `DeltaE_v / DeltaE_v,max = f(delta)` with `delta = X - X_b`. | `references/Chew_equations.md`, Eqs. (11)-(13), Table 2, Table 3 | `references/Chew2013.md`, Secs. 3.2-3.3 provide the interpretation and valid range. | The untraceable high-TS polynomial currently embedded in `core/model.py`. |
| Critical-point logic | Use the Chew critical point `(x_crit, y_crit)` to switch from early-stage linear correlation to the common polynomial branch. | `references/Chew2013.md`, Table 2 and Table 3 | `references/Chew_equations.md`, Table 3 transcription | A single global polynomial over the whole moisture range for high-solids SMP. Chew explicitly warns against that. |
| SMP shrinkage | Use the Chew high-solids linear shrinkage relation `D/D0 = a + b (X - X_b)` for SMP. | `references/Chew_equations.md`, Table 1 | `references/Chew2013.md`, Sec. 3.2 explains why linear shrinkage is preferred for high-solids milk. | Perfect shrinkage or balloon shrinkage as the SMP baseline. |
| Particle temperature balance | Use the Langrish axial particle heat balance `dT_p/dh`. | `references/Langrish_parallel-flow design_eq.md`, Eq. (36) | `references/foods_equations.md`, Eq. (7) is a time-domain cross-check only. | Direct reuse of the current lumped `dTp/dt` structure. |
| Air humidity balance | Use the axial air moisture balance `dY/dh`. | `references/Langrish_parallel-flow design_eq.md`, Eq. (41) | `references/foods_equations.md`, Eq. (6) confirms the coupling form in time coordinates. | Treating air humidity as constant unless a debug flag is set. |
| Air energy state | Use humid-air enthalpy `H_h` as the differential gas-side energy state, not air temperature directly. | `references/Langrish_parallel-flow design_eq.md`, Eq. (42) | `references/Langrish_coarsest_scale_modelling_eq.md`, Eqs. (1), (4), (17) provide the enthalpy definition and inversion basis. | Direct `dT_a/dh` as the primary air-side state in the clean baseline. |
| Air enthalpy closure | Use `H_h = C_pa (T_a - T_ref) + Y [lambda + C_pv (T_a - T_ref)]` and invert algebraically for `T_a`. | `references/Langrish_coarsest_scale_modelling_eq.md`, Eqs. (1), (4) | `references/foods_equations.md`, Eq. (8) shows the alternative `dT_b/dt` route and why enthalpy is cleaner. | Hidden latent/sensible split inside a direct temperature ODE. |
| Heat loss | Include `Qloss` as a distributed chamber sink in the gas enthalpy balance: `Qloss'(h) = UA/L * (T_a - T_amb)`. | `references/Langrish_parallel-flow design_eq.md`, Eq. (42) | `references/foods_equations.md`, Eq. (10) confirms the same chamber-level form. | A post-hoc outlet correction or a per-particle sink tied to droplet count. |
| Transport closure | Use `Re`, `Sc`, `Sh`, `Pr`, `Nu` from Langrish / Ranz-Marshall. | `references/Langrish_parallel-flow design_eq.md`, Eqs. (23)-(25), (33)-(38) | `references/foods_equations.md`, Appendix A is a cross-check with different fitted constants. | Mixing transport correlations from different sources in the same baseline without justification. |
| Mass-transfer coefficient basis | Compute `h_m` for the Chew vapor-density driving force from Sherwood closure, i.e. use the Langrish transport closure but keep the Chew density-based REA law. | `references/Chew_equations.md`, Eq. (1); `references/Langrish_parallel-flow design_eq.md`, Eqs. (32)-(35) | none | Mixing Chew vapor-density driving force with Langrish pressure-based `K_p` in the same mass-flux equation. |
| Equilibrium moisture `X_b` | Keep `X_b` as an algebraic closure and evaluate it from the Langrish skim-milk sorption relation at the local gas condition: `X_b = 0.1499 exp[-2.306e-3 T_a,K] [ln(1/RH_a)]^0.4`. | `references/Langrish_coarsest_scale_modelling_eq.md`, Eq. (11) | `references/foods_equations.md`, Eq. (11) is a low-RH coconut-milk approximation only. | The current GAB + free offset combination as baseline physics. |
| Optional `X_b` candidate for sensitivity tests | Keep a second, optional temperature-dependent GAB closure for SMP and compare its impact on `delta = X - X_b`, `DeltaE_v`, and outlet predictions: `X_b = (C(T) K(T) m_0 RH) / ((1-K(T)RH)(1-K(T)RH + C(T)K(T)RH))`, with `m_0 = 0.06156`, `C(T)=0.001645 exp(24831/(RT))`, `K(T)=5.710 exp(-5118/(RT))`. | `references/Lin_eq_gab.md` extracted from Lin, Chen, Pearce (2005), *Journal of Food Engineering* 68, 257-264 | `core/model.py`, lines 239-247, matches the same coefficient set already used in the legacy kernel | Do not make this the sole production baseline before comparing its effect against the Langrish closure in the new `h`-based kernel. |

## Combined equations selected for the new kernel

The new kernel should use the following hybrid reference set.

### 1. Particle mass balance

From Chew REA, converted to axial form using the Langrish `h` coordinate:

```math
\frac{dm_p}{dh}
=
- \frac{h_m A_p}{U_p}\left(\rho_{v,s} - \rho_{v,a}\right)
```

with

```math
\rho_{v,s} = \psi \rho_{v,sat}(T_p)
\qquad
\psi = \exp\left(-\frac{\Delta E_v}{R T_p}\right)
```

where the local reduced moisture is evaluated as

```math
\delta(h) = X(h) - X_b(h)
```

with the equilibrium moisture closure

```math
X_b(h) =
0.1499 \exp\left[-2.306 \times 10^{-3} T_{a,K}(h)\right]
\left[\ln\left(\frac{1}{RH_a(h)}\right)\right]^{0.4}
```

and

```math
\Delta E_v = f_{SMP}(X - X_b; X_0)\,\Delta E_{v,max}
```

```math
\Delta E_{v,max}
=
-R T_a \ln\left(\frac{\rho_{v,a}}{\rho_{v,sat}(T_a)}\right)
```

Because `m_p = m_s (1 + X)` and `m_s` is constant for a representative droplet:

```math
\frac{dX}{dh} = \frac{1}{m_s}\frac{dm_p}{dh}
```

### 2. Particle heat balance

Use the Langrish axial particle heat balance:

```math
\frac{dT_p}{dh}
=
\frac{\pi d_p k_a Nu (T_a - T_p) + \frac{dm_p}{dh} U_p H_{fg}}
{m_s (C_{ps} + X C_{pw}) U_p}
```

### 3. Air humidity balance

Avoid explicit droplet counting in the public kernel interface by collapsing the representative-droplet balance to total dry-solids flow:

```math
\frac{dY}{dh}
=
- \frac{\dot m_s}{\dot m_{da}} \frac{dX}{dh}
```

This is equivalent to Langrish Eq. (41) once `\dot m_s = \dot N_p m_s`.

### 4. Air enthalpy balance

Use humid-air enthalpy as the gas-side differential state:

```math
\frac{dH_h}{dh}
=
- \frac{\dot m_s}{\dot m_{da}} (C_{ps} + X C_{pw}) \frac{dT_p}{dh}
- \frac{Qloss'(h)}{\dot m_{da}}
```

with

```math
Qloss'(h) = \frac{UA}{L}(T_a - T_{amb})
```

and algebraic inversion

```math
H_h = C_{pa}(T_a - T_{ref}) + Y[\lambda + C_{pv}(T_a - T_{ref})]
```

### 5. Particle velocity

Use a 1D axial particle momentum equation:

```math
\frac{dU_p}{dh}
=
\left[
\left(1 - \frac{\rho_a}{\rho_p}\right) g
- \frac{3}{4}\frac{\rho_a C_D U_R (U_p - U_a)}{\rho_p d_p}
\right]\frac{1}{U_p}
```

with

```math
U_R = |U_p - U_a|
```

For the clean first kernel, radial and tangential particle motion are excluded from the baseline.

## Recommended simplifications for the first clean kernel

These simplifications are acceptable for the first rebuild and remain traceable to the reference set.

1. Single representative axial droplet class

Reason:
The user priority is a clean stationary SMP kernel, not a full droplet population balance.

2. 1D axial momentum only

Reason:
Radial and tangential trajectory equations matter for wall-deposition and spray-pattern work, but are not required to build a clean axial SMP drying core.

3. Air temperature derived from `H_h` and `Y`

Reason:
This is closer to the Langrish gas-side formulation and avoids an error-prone direct air-temperature ODE.

4. `X`, `Y`, and enthalpy all on dry bases

Reason:
Both Chew and Langrish use these bases naturally, and it avoids repeated wet/dry conversions.

5. SMP validity range explicitly bounded by the cited correlations

Reason:
Chew does not support a single unlimited SMP envelope in the cited material. The REA interpolation logic is supported in the 30-43 wt range, while the explicit shrinkage anchors are given for 37, 40, and 43 wt. Extrapolation to 50 wt should not be silent in the clean baseline.

6. Optional `X_b` sensitivity branch instead of immediate replacement

Reason:
Because Chew needs `X - X_b` but does not provide the `X_b(T,RH)` closure itself, it is reasonable to keep one baseline `X_b` relation and one optional GAB candidate for structured comparison before locking the production choice.

## Explicit exclusions for the clean rebuild

The following should be rejected as baseline physics for the new stationary kernel.

1. Lumped time-domain residence-time closure

The current kernel estimates an "effective residence time", then maps time to height afterwards. That is not the same as solving the axial balances.

2. Display velocity used inside transfer closure

Using a presentation-level velocity to compute `Re`, `Nu`, and `Sh` breaks the physical meaning of the transport closure.

3. Mixed SMP material curve assembled from undocumented coefficients

The legacy kernel blends Chew-like low-TS terms with an additional high-TS polynomial that is not traceable to the declared reference set.

4. Perfect / balloon shrinkage as the SMP baseline

Chew explicitly prefers linear shrinkage for high-solids milk and notes the limitations of the simplistic alternatives.

5. Ad-hoc early-stage REA ramps

Any hardcoded "start drying after N percent progress" logic should be removed unless directly supported by a cited material correlation.

6. Baseline calibration knobs inside the physics core

`rea_transfer_scale` and `equilibrium_moisture_offset` may be useful later in a calibration layer, but they should not define the clean reference kernel.

7. Foods dynamic equations as the primary formulation

They are useful as a cross-check that REA + 1D coupling is standard, but they are not the primary source for the SMP stationary core.

## Legacy items in `core/model.py` that should not be carried over

The current file is useful only as an implementation artifact to mine for IO shape and existing UI coupling.

The following legacy constructs are explicitly outside the clean baseline:

- `effective_residence_time_s` and `display_velocity_ms`
- `_particle_diameter()` anchor logic at 20, 30, and 50 wt%
- `_material_factor()` mixed polynomial logic and progress-based zero ramp
- direct air-temperature ODE instead of an enthalpy state
- GAB equilibrium with manual offset
- global transfer scaling inside the physics kernel

## Result

For the next implementation step, the clean reference split is:

- `Chew`: SMP REA material law and SMP shrinkage law
- `Langrish`: stationary axial balance structure, velocity, transport closure, `dY/dh`, `dH_h/dh`, `Qloss`
- `foods`: cross-check only
