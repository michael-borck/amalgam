# ADR-021: Dual-Rod Motion System (Reference Specification)

## Status
Accepted

## Supersedes
- ADR-003: Precision Smooth Rods
- ADR-020: Dual-8 Scavenger Variant

## Context

### Evolution of Thinking

**ADR-003** established M10 smooth rods as the reference specification based on:
- 2.4× stiffness advantage over M8
- Adequate rigidity for 220mm build volume at 330mm span (see ADR-024)
- Single-rod-per-axis simplicity

**ADR-020** proposed a "Dual-8 Scavenger" variant after analyzing the Voron Legacy, which achieves acceptable performance with 8mm rods at 200mm build volume. The key insight was that **dual rods sharing load halve deflection**, potentially enabling 8mm rods at Amalgam's larger build volume.

### The Physics Discovery

Beam deflection follows: `δ = F × L³ / (48 × E × I)`

When two parallel rods share the load equally:
- Each rod carries F/2
- Deflection: `δ_dual = (F/2) × L³ / (48 × E × I) = δ_single / 2`

| Configuration | Deflection @ 360mm, 280g | Verdict |
|---------------|--------------------------|---------|
| Single 8mm | 0.066mm | Excessive |
| Single 10mm | 0.027mm | Acceptable |
| **Dual 8mm** | **0.033mm** | **Acceptable** |

**Dual 8mm deflects MORE than a single 10mm, not less.** An earlier revision of
this ADR claimed the opposite. That was wrong, and the error mattered: stiffness
scales with the fourth power of diameter, so the comparison is:

```
dual-8    = 2 × 8⁴  =  8192   (arbitrary stiffness units)
single-10 = 1 × 10⁴ = 10000
ratio     = 8192 / 10000 = 0.819
```

Dual-8 is **81.9% as stiff** as single-10, which means it deflects **~22% more**
(0.033mm vs 0.027mm above). Lower stiffness produces more deflection, so the load
sharing does *not* "more than compensate" — it compensates for going down from
10mm to 8mm, and no more.

Because the ratio `2 × 8⁴ / 10⁴` is constant, **no span makes dual-8 stiffer than
single-10**. The comparison is span-independent; only the absolute magnitudes move.

The numbers in the table were always correct. The prose contradicted them.

### What Actually Justifies Dual-8

At Amalgam's reference bed (220×220mm, 280mm span, 280g Pitan):

| Configuration | Deflection | Verdict | Rod cost |
|---------------|-----------|---------|----------|
| Dual 8mm | 0.0156mm | Good | $0 (scavenged) |
| Single 10mm | 0.0128mm | Excellent | ~$60-80 AUD (purchased) |

Both configurations sit comfortably inside the 0.025mm quality threshold. The
22% difference is immaterial at the reference bed, and **the rods are free**.

Dual-8 is therefore the correct choice on cost, not on stiffness. The case breaks
down at larger spans, where the two configurations diverge toward the threshold:
at a 330mm span dual-8 reaches 0.0256mm (acceptable, at the threshold edge) while
single-10 stays at 0.0209mm (good). **Builders exceeding 220mm should treat this
as a real trade-off
rather than a free upgrade** — either buy M10, or shorten the span.

### The Scavengeability Argument

Amalgam already requires **two donor printers** for triple-Z (ADR-005):
- 6-7 NEMA17 motors needed (X, Y×2, Z×3, extruder)
- Most donor printers have 4-5 motors
- Two donors are the practical minimum

Given two donors are required anyway:
- Two Prusa clones provide 12× 8mm smooth rods
- M10 smooth rods are rarely scavengeable
- Buying M10 adds $60-80 AUD to build cost
- At the reference bed both configurations are within tolerance, so the free
  option wins on cost

**The scavenger path became the optimal path — on cost, not stiffness.**

## Decision

We adopt **Dual 8mm Smooth Rods with Vertical Stacking** as the Amalgam reference specification for XY motion.

This is chosen for **scavengeability and cost**, not for stiffness. Dual 8mm is
81.9% as stiff as a single 10mm rod (see above) and deflects ~22% more; at the
220mm reference bed both are within tolerance, and the 8mm rods are free from
two donors while M10 must be purchased.

### Reference Configuration

**X-Axis: Two 8mm rods, vertically stacked**
```
═══════════════════════════════════  Top rod
        [Plough carriage]
═══════════════════════════════════  Bottom rod
        ↑ ~30mm spacing ↑
```

**Y-Axis: Two 8mm rods per side, vertically stacked**
```
Left Y-rail:              Right Y-rail:
  ║══ 8mm ══║               ║══ 8mm ══║
  ║  belt   ║               ║  belt   ║
  ║══ 8mm ══║               ║══ 8mm ══║
    LM8LUU                    LM8LUU
```

**Z-Axis: Two 8mm rods (unchanged from ADR-003)**
- Vertical orientation
- Lower load than XY (bed weight distributed across triple-Z)

### Why Vertical Stacking?

For pure gravitational sag, vertical and horizontal stacking are equivalent—both share the load equally.

The difference is **moment resistance**:

| Orientation | Resists | Vulnerable to |
|-------------|---------|---------------|
| Horizontal | Yaw (twist L↔R) | Pitch (nose-dive) |
| Vertical | Pitch (nose-dive) | Yaw (twist L↔R) |

**Vertical stacking is preferred because:**
1. Pitch forces from Y-acceleration dominate toolhead dynamics
2. Belt runs cleanly between stacked rods
3. Validated by Voron Legacy design
4. X-end brackets are more compact vertically

### Rod Count Summary

| Axis | Previous (ADR-003) | New Reference |
|------|-------------------|---------------|
| X | 2× M10 | 2× M8 (vertical stack) |
| Y | 2× M10 | 4× M8 (2 per side, stacked) |
| Z | 2× M10 | 2× M8 |
| **Total XYZ** | **6 rods** | **8 rods** |

### Bearing Summary

| Location | Previous | New Reference |
|----------|----------|---------------|
| X carriage | 4× LM10UU | 4× LM8LUU (recommended) |
| Y gantry (total) | 4× LM10UU | 8× LM8UU (4 per side) |
| Z axis | 4× LM10UU | 4× LM8UU |
| **Total** | **12× LM10UU** | **4× LM8LUU + 12× LM8UU** |

See **ADR-022: Linear Bearing Selection** for detailed bearing rationale, scavenged bearing protocol, and alternative options (IGUS, printed bearings).

## Consequences

### Benefits

1. **True scavengeability**: All smooth rods from 2 donor printers
2. **Cost reduction**: Eliminates $60-80 AUD rod purchase
3. **Adequate stiffness**: At the 220mm reference bed, dual 8mm deflects
   0.0156mm vs single-10's 0.0128mm — both within the 0.025mm quality threshold
4. **Proven design**: Vertical stacking validated by Voron Legacy
5. **Parts availability**: 8mm rods/bearings are ubiquitous
6. **Aligned with triple-Z**: Already need 2 donors for motors

### Trade-offs

1. **More parts**: 8 rods + 16 bearings vs 6 rods + 12 bearings
2. **Redesigned brackets**: X-ends and Y-pucks need dual-rod mounts
3. **Toolhead mass budget**: Keep under 280g for optimal performance
4. **Slightly more complex assembly**: More rods to align
5. **~22% more deflection than single 10mm**: Dual 8mm is 81.9% as stiff as
   single-10 (2 × 8⁴ / 10⁴). Immaterial at the 220mm reference bed, but the gap
   widens with span — at 330mm dual-8 hits 0.0256mm vs single-10's 0.0209mm.
   Beyond 220mm beds, buy M10 or shorten the span.

### What This Enables

- **Sub-$250 AUD builds**: When fully scavenging from 2 donors
- **$300 target easily achieved**: Even with MKS SKIPR + CANbus upgrade
- **Lower barrier to entry**: No need to source obscure M10 precision rods
- **Better alignment with RepRap philosophy**: Use what you have

## Alternative Paths (Still Supported)

The parametric CAD system supports alternative configurations:

### M10 Single-Rod (Legacy Reference)
```python
SMOOTH_ROD_DIA = 10.0
SMOOTH_ROD_CONFIG = "SINGLE"
```
- For builders purchasing new rods
- Fewer parts, simpler assembly
- ~$60-80 AUD additional cost

### M8 Single-Rod (Budget/Compact)
```python
SMOOTH_ROD_DIA = 8.0
SMOOTH_ROD_CONFIG = "SINGLE"
```
- Limited to ~200mm build volume
- Single donor may suffice
- Marginal deflection at 235mm span

### MGN12 Linear Rails (Tinker Path)
```python
LINEAR_MOTION = "MGN12"
```
- For high-speed experiments (200mm/s+)
- Requires rail purchase (~$150-200 AUD)
- Different bracket designs

## BOM Implications

### Reference Build: Two Prusa Clone Donors

**Scavenged:**
| Part | Quantity | Source |
|------|----------|--------|
| 8mm smooth rods | 8-10 | Donors (12 available) |
| LM8UU bearings | 16 | Donors (24 available) |
| NEMA17 motors | 7 | Donors (8-10 available) |
| Heated bed | 1 | Best of 2 donors |
| Power supply | 1 | Best of 2 donors |

**Purchased:**
| Part | Cost (AUD) |
|------|------------|
| M10 threaded rod (frame) | $45 |
| MKS SKIPR + EBB36 + ADXL | $130 |
| E3D V6 clone hotend | $15 |
| Belts, pulleys, hardware | $30 |
| **Total** | **~$220** |

### Cost Comparison

| Configuration | Rod Cost | Total Build |
|---------------|----------|-------------|
| **Dual 8mm (reference)** | **$0** | **~$220** |
| Single M10 | $70 | ~$290 |
| MGN12 rails | $150 | ~$370 |

## Implementation Notes

### Deflection Thresholds

Based on layer height and quality requirements:

| Deflection | Verdict | Suitable For |
|------------|---------|--------------|
| < 0.015mm | Excellent | All applications |
| < 0.025mm | Good | Standard printing |
| < 0.035mm | Acceptable | Most printing |
| < 0.050mm | Marginal | Draft quality |
| > 0.050mm | Excessive | Not recommended |

These are implemented as the thresholds in `scripts/analysis/rod_sag.py` and are
covered by `scripts/tests/test_rod_sag.py`.

### Toolhead Mass Budget

For acceptable deflection (< 0.035mm) at 360mm span with dual 8mm:

| Toolhead | Mass | Deflection | Verdict |
|----------|------|------------|---------|
| Pitan + pancake NEMA17 | ~220g | 0.026mm | Acceptable |
| Pitan + standard NEMA17 | ~280g | 0.033mm | Acceptable |
| Wade + standard NEMA17 | ~400g | 0.047mm | Marginal |

**Recommendation:** Use pancake NEMA17 on extruder for best results.

### Span Calculations

For 220mm build volume (reference spec, see ADR-024), the analysis tool derives
the X span from the frame sizing constants:
```
X-span = BUILD_X + MOTOR_CLEARANCE = 220 + 60 = 280mm
```

At this span with a 280g Pitan on dual 8mm, deflection is 0.0156mm (good). See
ADR-024 for the note on an earlier revision that assumed a 330mm span.

### CAD Parameters

```python
# Reference specification (Dual 8mm)
SMOOTH_ROD_DIA = 8.0
SMOOTH_ROD_CONFIG = "DUAL_VERTICAL"
BEARING_TYPE = "LM8UU"  # or "LM8LUU" for long bearings

# Derived
X_ROD_COUNT = 2  # vertically stacked
Y_ROD_COUNT = 4  # 2 per side, stacked
Z_ROD_COUNT = 2
TOTAL_SMOOTH_RODS = 8
```

### Assembly Sequence

1. **Y-rails first**: Install dual rods on each Y-rail assembly
2. **Verify parallelism**: Rods must be parallel within 0.1mm over length
3. **X-gantry**: Mount X-end brackets to Y-rails
4. **X-rods**: Install vertical stack, verify spacing
5. **Plough carriage**: Install with bearings on both rods
6. **Belt routing**: Run belts between stacked rods

## Quality Verification

### Rod Quality
- **Spec**: Precision ground, hardened steel
- **Test**: Roll LM8UU bearing along rod—should be smooth, no grinding
- **Measure**: Verify 8.00mm ± 0.01mm diameter with calipers

### Parallelism Check
- Measure rod spacing at both ends
- Should be equal within 0.1mm
- Adjust bracket mounting if needed

### Load Test
- With toolhead at center of X travel
- Measure deflection with dial indicator
- Should be < 0.05mm under static load

## References

- ADR-003: Precision Smooth Rods (superseded—historical reference)
- ADR-005: Triple-Z Independent Kinematic Leveling
- ADR-020: Dual-8 Scavenger Variant (superseded—merged into this ADR)
- ADR-022: Linear Bearing Selection (companion ADR for bearing choices)
- ADR-024: Heated Bed Size Selection (defines 220mm reference build volume)
- [Voron Legacy](https://vorondesign.com/voron_legacy): Vertical stacking validation
- [Beam Deflection Theory](https://en.wikipedia.org/wiki/Deflection_(engineering))
- [../philosophy.md](../philosophy.md): "Tractor with a Racecar Brain"
- Analysis conversation: "Voron Legacy Comparison" (2025-01-27)
