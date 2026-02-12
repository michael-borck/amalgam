# Printed Frame Printers and the Case for Steel Rod Frames

How open-source printed-frame printers validate the Amalgam's "Tractor with a Racecar Brain" philosophy — and where printed frames hit their limits.

## The Spectrum of DIY Printer Frames

The 3D printing community has explored a fascinating range of frame construction approaches, from fully printed structures through to traditional aluminum extrusion. Each approach reveals something about where plastic works as a structural material and where it doesn't — insights that directly informed the Amalgam's design.

## The Rook (Rolohaun Design)

The Rook MK1 is a small, beginner-friendly CoreXY with a **fully 3D printed frame**. The Rook Evolution expands this to a 150×150×160mm build area within a 304×304mm external footprint. Print settings are modest: 0.2mm layer height, 4 walls, 30% infill.

The Rook works because it keeps spans short. At ~300mm per side, printed structural members in PLA or PETG are stiff enough for the forces involved. The design stays within the envelope where plastic's lower Young's modulus (2–3 GPa vs aluminum's 70 GPa) simply doesn't matter — deflection is negligible at these spans under these loads.

Notably, there's also a **Rook 2020** variant (by Kanrog) that swaps the printed frame for 2020 aluminum extrusion — acknowledging that once you want to go bigger or stiffer, metal is the pragmatic choice.

- **Rook MK1**: [Printables](https://www.printables.com/model/387431-rook-mk1-3d-printer)
- **Rook Evolution**: [MyMiniFactory](https://www.myminifactory.com/object/3d-print-rook-evolution-fortress-corexy-3d-printer-289167)
- **Rook 2020**: [Printables](https://www.printables.com/model/447255-rook-2020-mk1)

## The T100 (Matthäus Szturc)

The T100 (formerly "The 100") took a different approach to the printed frame problem. Rather than trying to make the frame ultra-rigid, Szturc focused on **centre of gravity management** — carefully placing heavy components in balanced positions to minimise vibration. This allowed the motion system to run at extreme speeds (sub-6-minute Benchys) despite a printed frame that would flex under traditional loading patterns.

The T100 has a build volume of roughly 165×165×165mm and was designed for accelerations up to 100,000 mm/s², later pushed to 150,000 mm/s² in v1.1. It proved that a printed frame can work for high-speed printing if you manage dynamics rather than fighting material stiffness.

Key insight: **rigidity isn't the only path to print quality.** If you can't make the frame stiff, make sure it doesn't resonate.

- **T100**: [GitHub](https://github.com/MSzturc/the100) | [Printables](https://www.printables.com/model/572689-the-100-v11-the-fastest-3d-printer-based-on-a-prin)

## The T250 (Matthäus Szturc)

The successor to the T100, the T250 was designed from scratch to handle **250,000 mm/s² acceleration** — the "250" refers to acceleration capability, not build volume. Szturc kept 250mm gantry rods (which he considers the sweet spot for fast, reliable printing) while increasing build volume to 192×212×175mm — a 60% increase over the T100 without adding gantry weight.

The T250 uses a rod-based gantry motion system (smooth rods, not linear rails) with a 4-motor CoreXY layout for 50–60% more acceleration than a 2-motor system. The frame is still printed but redesigned to absorb extreme forces without needing to be anchored to a table.

The T250 demonstrates both the potential and the ceiling of printed frames. At this performance level, every gram of gantry weight matters, every resonance must be managed, and the frame design becomes an exercise in vibration engineering rather than simple structural stiffness.

- **T250**: [GitHub](https://github.com/MSzturc/T250) | [Printables](https://www.printables.com/model/1341051-t250-the-worlds-fastest-3d-printer)

## Chip Jones: Printed Extrusion with Embedded Rods

An earlier and often overlooked project by Chip Jones took yet another approach: **3D printing copies of aluminum extrusion profiles** for a printer frame (based on an Anet A8 / Prusa i3 layout). The clever part was that the centre of each printed extrusion had an 8mm hole running its full length, allowing a plain steel smooth rod to be inserted for added rigidity.

In practice, Jones only used the embedded rods in the Z-axis sections (the tallest spans), which was enough. He also developed butt connectors so shorter printed sections could be joined end-to-end to create longer frame members — addressing the print bed size limitation.

This is a direct precursor to the "threaded rod reinforcement" concept: a printed shell provides geometry and mounting interfaces, while an embedded steel rod provides the actual structural stiffness. The printed part handles compression; the rod handles tension and bending.

- **Chip Jones' printed extrusion frame**: [Hackaday write-up](https://hackaday.com/2018/02/03/3d-print-a-3d-printer-frame/)

## Where Printed Frames Break Down

All of these projects converge on a common finding: **printed frames work well up to about 300mm span length.** Beyond that, the stiffness gap between thermoplastics and metal becomes increasingly problematic:

- **Deflection scales with the cube of span length.** Doubling span increases deflection 8×. At 200mm, the difference between PETG and aluminum is unmeasurable. At 400mm+, you can feel it.
- **Resonance frequency drops with longer spans.** A shorter, stiffer frame resonates at higher frequencies that are easier to filter with input shaping. Longer printed frames resonate at lower frequencies that input shapers struggle with.
- **Thermal stability decreases.** Longer printed spans in enclosed heated chambers (needed for ABS/ASA) soften and creep over time. This isn't an issue at small scale or with open frames.

The Rook 2020 variant and Szturc's gantry rod lengths (capped at 250mm) both acknowledge these limits implicitly.

## How This Informs the Amalgam

The Amalgam's "Tractor with a Racecar Brain" philosophy addresses the same core problem from the opposite direction:

| Approach | Frame | Brains | Sweet Spot |
|---|---|---|---|
| Rook / T100 / T250 | Printed (flexible) | Klipper (input shaping, pressure advance) | Small build volume, extreme speed |
| Chip Jones | Printed + embedded rods | Standard firmware | Medium build volume, moderate speed |
| Traditional Voron / RatRig | Aluminum extrusion | Klipper | Large build volume, high speed |
| **Amalgam** | **Steel threaded rod (M10)** | **Klipper** | **Large build volume, heavy/reliable** |

The Amalgam skips the printed frame entirely for primary structure. M10 steel threaded rods are cheap, universally available, and provide stiffness that no amount of printed plastic can match at larger scales. Printed parts serve as **interfaces** — motor mounts, bearing holders, clamps — not as structural members.

This is the logical extension of what Chip Jones demonstrated: if you're going to embed a steel rod inside a printed shell for stiffness, and the shell isn't contributing meaningfully to rigidity at larger spans, why print the shell at all? Just use the rod as the frame and design clamps to mount things to it.

The result is a printer that:

- Scales to large build volumes without frame stiffness concerns
- Uses parts-bin hardware (threaded rod, nuts, washers) that costs almost nothing
- Relies on Klipper's input shaping to handle whatever resonances the frame produces
- Keeps printed parts in roles where plastic excels: complex geometry, iteration speed, and low-stress mounting interfaces

The printed frame printers proved that clever software (Klipper) can compensate for frame flexibility. The Amalgam takes that lesson and combines it with a frame material that doesn't need compensating — giving Klipper a head start rather than asking it to make up for structural compromises.
