# Amalgam

<!-- BADGES:START -->
[![3d-printing](https://img.shields.io/badge/-3d--printing-blue?style=flat-square)](https://github.com/topics/3d-printing) [![cad](https://img.shields.io/badge/-cad-blue?style=flat-square)](https://github.com/topics/cad) [![configuration](https://img.shields.io/badge/-configuration-blue?style=flat-square)](https://github.com/topics/configuration) [![diy](https://img.shields.io/badge/-diy-blue?style=flat-square)](https://github.com/topics/diy) [![klipper](https://img.shields.io/badge/-klipper-blue?style=flat-square)](https://github.com/topics/klipper) [![maker](https://img.shields.io/badge/-maker-blue?style=flat-square)](https://github.com/topics/maker) [![parametric-design](https://img.shields.io/badge/-parametric--design-blue?style=flat-square)](https://github.com/topics/parametric-design) [![python](https://img.shields.io/badge/-python-3776ab?style=flat-square)](https://github.com/topics/python) [![reprap](https://img.shields.io/badge/-reprap-blue?style=flat-square)](https://github.com/topics/reprap) [![salvage](https://img.shields.io/badge/-salvage-blue?style=flat-square)](https://github.com/topics/salvage)
<!-- BADGES:END -->

### A 2026 RepRap Reference Specification

**High-Mass, Low-Cost, Total Control.**

---

## The Tractor is Coming

Amalgam is a scavenger-friendly 3D printer — a high-mass, fully parametric machine built from two donor printers and open-source intelligence. The name reflects its nature: an amalgam of salvaged parts merged into something new.

**Website:** [theamalgam.org](https://theamalgam.org)

**Expected Release:** End of 2026

---

## The Philosophy

We build a **"Tractor with the Brain of a Racecar"** — using heavy, high-torque, battle-tested hardware and giving it extreme precision through Klipper.

| Feature | Target |
|---------|--------|
| **Price** | < $300 AUD |
| **Build Volume** | 220×220×220mm |
| **Accuracy** | ±0.1mm |
| **Speed** | 70–120mm/s |
| **Control** | 100% Local, No Cloud |

---

## Quick Start

> **Before you build:** Read [SAFETY.md](SAFETY.md). You're building a machine from salvaged parts that involves mains power, hot surfaces, and moving parts.

### Option 1: Configuration Wizard (Recommended)

```bash
git clone https://github.com/the80-20workshop/amalgam.git
cd amalgam

# Run the wizard - it asks what donor printers you have
python scripts/wizard.py
```

The wizard:
1. Asks what donor printers you have
2. Recommends a frame path (Scaffold, Mill, or Lathe)
3. Generates `config.py` for your specific build
4. Runs engineering analysis

### Option 2: Quick Analysis

```bash
# See what the reference spec looks like
python scripts/analyze.py --quick

# Explore trade-offs (what if M8 rods? what if 200x200 bed?)
python scripts/whatif.py --compare-rods
python scripts/whatif.py --compare-beds
```

### Option 3: Build Parts

```bash
cd cad
./setup.sh        # First time: creates venv, installs deps, configures
./build.sh build_all   # Build all parts
```

See [BUILDING.md](BUILDING.md) for complete guide.

---

## Frame Paths

Amalgam requires **two donor printers**. The frame path depends on what you scavenge:

| Path | Frame | Motion | Best Donors | Character |
|------|-------|--------|-------------|-----------|
| **Scaffold** | M10 Threaded Rod + MDF | Smooth Rods | Anet A8, Wanhao, Prusa i3 clones | Heritage — RepRap Darwin tribute |
| **Mill** | Aluminum Extrusion + MDF | V-Slots | Ender 3, CR-10, Voxelab Aquila | Zero-waste — use everything |
| **Lathe** | Aluminum Extrusion + MDF | Smooth Rods + IGUS | Ender 3 + bought rods, mixed | Precision — best motion quality |

**Cost:** ~$160-280 depending on path (Mill cheapest, Lathe ~$75 more for better motion).

**All paths share:** MDF base (squaring jig + damping), Triple-Z leveling, Pitan extruder, E3D V6, Klipper.

**Optional:** Add MKS SKIPR (~$130) for cleaner single-board electronics.

**Got one donor?** Just add Klipper to it. Amalgam requires two matching donors for a complete build.

---

## Documentation

| Document | Description |
|----------|-------------|
| [SAFETY.md](SAFETY.md) | **Read first** — Hazards and safety guidance |
| [docs/manifesto.md](docs/manifesto.md) | Quick-start overview |
| [docs/philosophy.md](docs/philosophy.md) | The "Tractor" philosophy and heritage |
| [REFERENCE-SPEC.md](REFERENCE-SPEC.md) | Hardware specification |
| [BUILDING.md](BUILDING.md) | Complete build guide |
| [scripts/README.md](scripts/README.md) | Build system documentation |
| [docs/adr/](docs/adr/) | Architecture Decision Records |
| [docs/reference/donor-printer-guide.md](docs/reference/donor-printer-guide.md) | Which printers to scavenge |

---

## The Lineage

We stand on the shoulders of giants:

* **[RepRap Darwin (2007)](https://reprap.org/wiki/Darwin):** Box-frame threaded-rod origin. Inspired our "Scaffold" frame path.
* **[RepRap Mendel (2009)](https://reprap.org/wiki/Mendel):** The "plough" X-carriage sled design.
* **[Prusa i3 Rework (2013)](https://www.thingiverse.com/thing:119616):** Greg's Wade geared extruder—ancestor of our Pitan.
* **[Voron Legacy](https://vorondesign.com/voron_legacy):** Dual 8mm rods with vertical stacking for X-Y gantry.
* **[Voron Trident](https://vorondesign.com/voron_trident):** Three-pillar Z-drop bed with Triple-Z leveling.
* **[The 100](https://github.com/MSzturc/the100) / [The Rook](https://github.com/Kanrog/Rook):** Klipper-first philosophy on DIY frames.

---

## Status

| Component | Status |
|-----------|--------|
| Philosophy & Manifesto | ✅ Complete |
| Build System (wizard, analysis, what-if) | ✅ Complete |
| build123d Parametric Parts | 🔧 In Development |
| Klipper Configurations | 🔧 In Development |
| Assembly Documentation | 🔧 In Development |
| Reference Build | ⏳ Planned |

---

## Stay Updated

⭐ **Star this repo** to follow development.

📬 **Discussions** will open closer to release.

---

## License

**GNU GPL v3** — The same license used by the original RepRap Darwin.

---

> *If you want a printer, buy one. If you want the Red Pill, build this.*
