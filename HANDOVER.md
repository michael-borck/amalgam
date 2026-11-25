# HANDOVER — Amalgam

**Written:** 2026-10-10
**Branch:** `main`
**Last commit:** `08e65c3 Update README badges`
**Working tree:** 29 uncommitted changes (see [Uncommitted work](#uncommitted-work))

---

## Read this first

Amalgam is a scavenger-friendly 3D printer specification. The design phase is
done; we are partway through turning it into parts you can actually print.

**The project is uncommitted.** Everything in the last several sessions exists
only in the working tree. Start by committing it — see
[Next actions](#next-actions).

If you're an LLM picking this up: read this file, then
[Key decisions](#key-decisions) and [Open questions](#open-questions). Don't
re-derive what's already settled.

---

## Current state in one table

| Area | Status |
|---|---|
| Documentation / ADRs | Complete (33 ADRs) |
| Analysis tools (`scripts/`) | Working, tested (58 tests) |
| CAD library (`cad/amalgam/lib/`) | Rewritten, verified (96 tests) |
| Frame parts | 6 of ~8 generating + exporting |
| X-axis motion | 3 parts generating + exporting |
| Y-axis motion | Not started |
| Bed / spider | Not started |
| Extruder | Not started |
| Triple-Z bottom corners | Implemented, **export script broken** |
| Klipper configs | Stale, needs rewrite |
| CI | Written, never actually run on GitHub |

---

## What works right now

```bash
# Analysis (stdlib only, fast)
python scripts/analyze.py --quick
python scripts/whatif.py --compare-rods

# Generate CAD parts
cd cad
cp config.py.example config.py    # if you don't have one
PYTHONPATH=. python amalgam/parts/frame/corner_standard.py
PYTHONPATH=. python amalgam/parts/frame/squaring_jig.py
PYTHONPATH=. python amalgam/parts/motion/x_axis.py

# Tests
python -m pytest scripts/tests/ -q    # 58 pass
cd cad && python -m pytest tests/ -q  # 96 pass
```

Note: `PYTHONPATH=.` is required when running part scripts directly.
`./build.sh build <name>` sets it for you.

### Parts that generate and export

| File | Copies | Notes |
|---|---|---|
| `corner_standard_bottom` | 4 | Through-bore; bed weight + Z thrust |
| `corner_standard_top` | 4 | Jam nut; rod doesn't protrude |
| `squaring_jig` | 1 | MDF jig, holds rods at true 90° |
| `x_gantry_beam` | 1 | Dual 8mm, 30mm vertical stack |
| `x_carriage` | 1 | "Plough", 8.2mm bearing bores |
| `x_end_plate` | 2 | Rod capture + M3 set screws |

---

## Key decisions

**Scaffold path, not Mill.** Frame is M10 *threaded* rod + printed corners
(ADR-001, ADR-025). `FRAME_PATH = "Scaffold"` in `cad/config.py.example`.

**Two different rod systems — don't confuse them:**

| Rod | Size | Job | Where |
|---|---|---|---|
| Skeleton | M10 **threaded** | Frame structure | Corner brackets |
| Motion | 8mm **smooth** | Linear motion | LM8UU bearings |

`SMOOTH_ROD_DIA` (motion) and `M10_FIT_DIA` (frame) are independent config
values. `M12_*` names are deprecated aliases kept for compatibility.

**Rod fit diameter is 10.5mm** (10mm nominal + 0.5 "lumpy factor" for zinc vs
galvanized variation). **Unverified** — needs measuring against real rod.

**Mixed anchoring** (the user's call):
- Bottom corners → through-bore. Nuts on the far side. Strongest, and these
  carry bed weight + Z-screw thrust.
- Top corners → jam nut. Lightly loaded, clean finish, rod doesn't protrude,
  and forgiving of imperfect rod cuts.

**Dual 8mm over single 10mm is justified on COST, not stiffness.** Dual 8mm
is 81.9% as stiff as single 10mm (`2 × 8⁴ / 10⁴`) and deflects ~22% *more*.
At the 220mm reference bed both are within the 0.025mm quality threshold, and
8mm rods are free from two donors while M10 must be bought (~$60-80 AUD).
Beyond 220mm the gap matters — see ADR-021.

**Reference spec numbers:** 220×220×220mm bed, ~280mm X span, dual 8mm,
Pitan 280g, ~4138 mm/s² recommended accel.

---

## Bugs found and fixed

These are worth knowing so they don't get reintroduced.

### 1. ADR-021 had the physics backwards (docs error, not code)

ADR-021 claimed "dual 8mm rods achieve LESS deflection than single 10mm."
False. Stiffness scales with `d⁴`, so `2 × 8⁴ < 10⁴` always. Dual-8 deflects
~22% more, at every span. The table numbers in the ADR were correct; the prose
contradicted them.

Corrected in ADR-021, ADR-020, ADR-003, REFERENCE-SPEC.md. `TestDualRodRelationship`
in `scripts/tests/test_rod_sag.py` now pins the true relationship.

### 2. Corner brackets were missing both Y-axis rod bores

`corner.py` built a Z-aligned cylinder, translated it, *then* called
`.rotate(Axis.Z, 90)`. Rotating about Z cannot reorient a Z-aligned cylinder —
it just teleported the centre, so both Y-axis bores landed on top of
existing holes and cut nothing. Volume was 38% of expected.

Fixed with `_axis_cylinder()`, which orients *first*, then translates.

**Lesson:** never translate then rotate. Build in the final orientation.

### 3. Three further CAD bugs found by the tests

- `create_nema17_motor_mount` listed one bolt position twice, omitting another
  → drilled 3 of 4 holes.
- Motor shaft bore was subtracted *before* unioning the plate → buried in
  solid material.
- Jam-nut blind bore was centred on the face instead of starting there.

### 4. `cad/config.py` was tracked despite being gitignored

`.gitignore:22` lists it, but it was already in the index, so the ignore never
applied — and a contributor's build config (MKS_SKIPR, 235mm bed) shipped to
everyone. **Staged for deletion** (`D cad/config.py` in `git status`). Keep it
that way.

### 5. My own broken verification checks

Worth recording because they nearly gave false confidence:

- First `assert_mirror_symmetry` compared **volumes**. Volume is invariant
  under mirroring for *any* shape, so it could never fail. It "passed" on a
  badly broken part.
- Second attempt probed a 7³ grid at ~8.3mm spacing — walked straight past a
  3.3mm bolt hole, and took 23s.
- Final version compares cross-sectional area and bounding extents, and was
  tested against known-good and known-bad shapes before being trusted.

**Lesson:** a check that cannot fail is not a check. Always test the test.

---

## How verification works

No rendering required. `cad/amalgam/lib/verify.py` provides assertions:

- `assert_point_empty/solid` — probe a point. Rod passages must be hollow.
- `assert_rod_passes_through` — builds the actual rod, asserts zero
  interference. Strongest available check.
- `assert_mirror_symmetry`, `assert_volume_reconciles`, `assert_single_solid`,
  `assert_no_self_intersection`
- `TestExportIntegrity` — reads generated STLs, catches degenerate tessellation

Point-probing is the core technique: **wherever a rod passes through, assert
that exact point is empty.**

---

## Next actions

In order. Items 1–3 are self-contained; item 4 needs hardware.

### 1. Commit the working tree

29 uncommitted files including new tests, CI, and the CAD rewrite. Verify
`cad/config.py` stays deleted from the index:

```bash
git status --short
git rm --cached cad/config.py   # if it reappears
git commit -m "..."
```

Suggested split: (a) analysis fixes + ADR corrections + tests, (b) CAD rewrite +
verification harness + tests, (c) CI workflow.

### 2. Fix `corner_front_left.py` — currently broken

```bash
cd cad && PYTHONPATH=. python amalgam/parts/frame/corner_front_left.py
# TypeError: make_motorized_corner() got an unexpected keyword argument 'location'
```

The rewritten `make_motorized_corner()` uses keyword args (`motor_axis`,
`anchoring`). Update the part script and export the Triple-Z bottom corners.
These are needed before the frame can carry the bed.

### 3. Build the Y-axis and bed parts

- `parts/motion/` — Y gantry, Y pucks (dual 8mm per side per ADR-021)
- `parts/bed/` — spider/hub (ADR-008, ADR-009)

Both directories are empty. `lib/motion.py` has the X-axis pattern to follow.

### 4. Print one `corner_standard_top` first

Deliberately the least critical part — it carries only the gantry. If the bore
or jam-nut pocket sizing is off, find out cheaply before committing to eight
brackets. Use fuzzy skin on cosmetic faces, keep mating surfaces smooth.

### 5. Measure real M10 rod

`LUMPY_FACTOR = 0.5` is a guess. Cheap galvanized rod varies more. Measure
actual diameter and update if needed. This affects every bracket.

### 6. Rewrite the Klipper configs (deferred deliberately)

`klipper/printer.cfg` is stale and contradicts current ADRs:

| File | Says | Should say |
|---|---|---|
| Extruder | Greg's Wade | Pitan (ADR-019) |
| `position_max` | 250 | 220 (ADR-024) |
| `max_accel` | 2000 | ~4138 |
| Input shaping | absent | ADXL345 is in the BOM |
| Host | Pi 3B+ | undecided |

**Why deferred:** pin assignments depend on a board you haven't chosen;
`rotation_distance` needs measurement; `PID_*` needs a heat-up curve. Writing
these now guarantees they're wrong. `get_klipper_settings()` in
`acceleration.py` now produces correct dual-8 values when you're ready.

---

## Open questions

**Blocking-ish:**

- Does a Scaffold build actually get 12× 8mm rods and 6-7 motors from two
  donors? Price is settled (~$50 or less); *quantity* is unverified. Cheap to
  check, and it invalidates the whole cost argument if it fails.
- Real M10 rod diameter (see action 5).
- Which control board? Drives every pin assignment.

**Design still open:**

- `ADR-024` assumes a 330mm X span; `frame_sizing.py` computes 280mm from its
  constants. ADR-024 was updated to document the 280mm derivation, but which is
  physically correct depends on the real frame layout. If it's 330mm, dual-8
  gives 0.0256mm (marginal) rather than 0.0156mm.
- The carriage lightening pocket is hypothetical until printed. It may be too
  aggressive for layer adhesion.
- Build volume is documented as 220×220×220mm. (REFERENCE-SPEC.md previously
  said "~250mm³"; that has been corrected.)

**Known cosmetic issue:** macOS creates AppleDouble `._*` files on this exFAT
drive ("Crucial X9"). They're gitignored and filtered from `utilities/list.py`,
but they reappear on every transfer. Delete with:
`find . -name "._*" -delete`

---

## Uncommitted work

Full list from `git status`. Grouped:

**Analysis + docs:**
`REFERENCE-SPEC.md`, `docs/adr/{003,020,021,024}-*.md`, `scripts/README.md`,
`scripts/analysis/{__init__,acceleration,frame_sizing,rod_sag}.py`,
`scripts/analyze.py`, `scripts/builders/{analysis_runner,config_builder}.py`,
`scripts/registry/{beds,compatibility}.py`, `scripts/whatif.py`,
`scripts/wizard.py`

**CAD:**
`cad/amalgam/lib/corner.py`, `cad/amalgam/lib/verify.py` (new),
`cad/amalgam/lib/motion.py` (new),
`cad/amalgam/parts/frame/{corner_standard,squaring_jig}.py`,
`cad/amalgam/parts/frame/squaring_jig.py` (new),
`cad/amalgam/parts/motion/x_axis.py` (new),
`cad/amalgam/parts/frame/corner_front_left.py` (**still broken**),
`cad/config.py.example`, `cad/utilities/list.py`, `.gitignore`

**New tests:** `scripts/tests/` (2 files), `cad/tests/` (2 files)

**CI:** `.github/workflows/ci.yml` (new, never run on GitHub)

**Deleted from index:** `cad/config.py`

---

## Environment

- Python 3.13, build123d 0.10.0
- `build123d` must be installed for CAD work; analysis is stdlib-only
- Working dir is on an external exFAT drive — see the `._*` note above
- Repo path contains a space: `/Volumes/Crucial X9/Projects/amalgam`. Quote paths.

## Testing caveat

CI was written but has never run on GitHub. Each step was executed locally and
passed, but the workflow itself is unverified — expect to fix something on first
push.

---

## Where the thinking went

A note for whoever picks this up: earlier sessions produced 21k lines of docs
against 10k lines of code, with three part categories empty. That's a lot of
theory for a machine that doesn't physically exist yet.

The recent sessions deliberately shifted that balance — the analysis was
corrected because it had real errors, then the CAD was rewritten and verified.
**The working rule now: no new ADRs. Build, print, and see what breaks.** An
unanswered question gets answered by making the part, not by writing about it.