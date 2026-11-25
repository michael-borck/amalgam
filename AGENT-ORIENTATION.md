# AGENT-ORIENTATION.md

**Read [HANDOVER.md](HANDOVER.md) first.** That file has the current state,
known bugs, and next actions. This one is a map for finding things.

---

## Don't re-derive these

They are settled. Re-deriving wastes a session.

- **Frame path:** Scaffold (M10 threaded rod + printed corners), not Mill.
- **Two rod systems:** M10 threaded = frame skeleton. 8mm smooth = motion.
  They are independent. Don't conflate them.
- **Dual 8mm vs single 10mm:** dual-8 is 81.9% as stiff and deflects ~22%
  MORE. Chosen on cost (free from donors), not stiffness. ADR-021 originally
  claimed the opposite; that's fixed. See `docs/adr/021-dual-rod-motion-system.md`.
- **Reference spec:** 220×220×220mm bed, ~280mm X span, dual 8mm,
  30mm vertical stack, Pitan 280g, ~4138 mm/s².
- **Bottom corners through-bore, top corners jam nut.** Deliberate split.

## Verify like this

Everything is testable without rendering or a printer:

```bash
python -m pytest scripts/tests/ -q    # analysis, 58 tests
cd cad && python -m pytest tests/ -q  # geometry, 96 tests
```

Geometry assertions live in `cad/amalgam/lib/verify.py`. The key technique is
**point probing**: wherever a rod passes through, assert that point is empty.

```python
assert_point_empty(part, (0, 20, 0), "Y+ rod passage")
assert_rod_passes_through(part, start, end, 10.5, "M10 rod")
```

**A check that cannot fail is not a check.** If you add a verification helper,
prove it catches a known-bad case before trusting it. Two checks were already
written this way that passed everything while detecting nothing.

## CAD gotchas that caused real bugs

- **Never translate then rotate.** A bare `Cylinder` is Z-aligned; rotating
  about Z can't reorient it, it just moves the centre. Orient first, then
  translate — see `_axis_cylinder()` in `cad/amalgam/lib/corner.py`.
- **Subtract after union.** Cutting a bore before adding a plate leaves it
  buried in solid material.
- Run part scripts with `PYTHONPATH=.` (or via `./build.sh`).

## Layout

```
scripts/          analysis + wizard (stdlib only, fast tests)
  analysis/       physics: rod_sag, frame_sizing, acceleration
  registry/       component database (boards, beds, extruders, motors)
  builders/       config + report generators
  tests/          58 tests

cad/              parametric CAD (needs build123d)
  amalgam/lib/    corner.py, motion.py, verify.py
  amalgam/parts/  frame/, motion/, bed/, extruder/, calibration/, victory/
  tests/          96 geometry tests
  config.py       generated, gitignored — never commit

docs/adr/         33 ADRs (design complete; no new ones)
klipper/          printer.cfg (stale), hardware.cfg + macros.cfg (empty)
.github/          CI (written, never run)
```

## Working rules

1. **No new ADRs.** Build and print instead. Open questions get answered by
   making the part.
2. **Test before claiming done.** Run the suite; don't eyeball geometry.
3. **Check `git status`** — a lot is uncommitted.
4. **CI has never run on GitHub.** Expect to fix it on first push.

## First three things to do

1. Commit the working tree (~29 files, nothing committed since `08e65c3`).
2. Fix `cad/amalgam/parts/frame/corner_front_left.py` (broken API call).
3. Print one `corner_standard_top` — least critical part, cheapest to get wrong.