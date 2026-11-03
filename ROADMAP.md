# Loyal Wingman Simulator (MUM-T) — Methodical Master Checklist

This document is the **systematic, step-by-step implementation plan** for advancing the `Simulation_Wingman` research platform. Each task is self-contained with explicit technical scope, affected files, acceptance criteria, and verification commands, executed strictly one by one.

---

## Progress Overview

```mermaid
flowchart TD
    P0["Phase 0: Foundation & Core Refactor [COMPLETED]"] --> P1["Phase 1: Cooperative Target Allocation (Hungarian Algorithm) [COMPLETED]"]
    P1 --> P1_5["Phase 1.5: Clean Code & SOLID Refactoring [COMPLETED]"]
    P1_5 --> P2["Phase 2: Dynamic Formations & Tactical Geometries [NEXT]"]
    P2 --> P3["Phase 3: Interactive Live Dashboard & Runtime Tuning"]
    P3 --> P4["Phase 4: Physical Ballistics & Kamikaze Evasion"]
    P4 --> P5["Phase 5: Monte Carlo Sweeps & LaTeX Paper Assets"]
```

---

## Phase 0: Architecture & Foundation Refactor `[COMPLETED]`

- [x] **STEP 0.1: Spatial Partitioning via Quadtree** (`8ae19b5`)
- [x] **STEP 0.2: Decoupled Camera & Viewport (`DisplayManager`)** (`27a6670`)
- [x] **STEP 0.3: Telemetry & Metrics Tracking (`ExperimentManager`)** (`cb05c28`)
- [x] **STEP 0.4: Profiling & Bottleneck Optimization** (`1f0141d`)
- [x] **STEP 0.5: Swarm Lifecycle Separation (`SwarmManager`)** (`9a6057f`)
- [x] **STEP 0.6: Headless Multi-Core PSO Runner (`headless_runner.py`)** (`9a6057f`)
- [x] **STEP 0.7: Modern Tactical HUD & Agent Inspector (`GUIManager`)** (`92aec49`)
- [x] **STEP 0.8: Native Laptop Resolution & 1:1 World Adaptation** (`ae9a3d6`)

---

## Phase 1: Cooperative Target Allocation (Hungarian Algorithm) `[COMPLETED]`

- [x] **STEP 1.1: Threat Priority & Global Cost Matrix Formulation** (`1fb222b`)
- [x] **STEP 1.2: Hungarian Algorithm (Munkres / Linear Sum Assignment) Integration** (`1fb222b`)
- [x] **STEP 1.3: Role Specialization (Interceptors vs. Close Escorts)** (`1fb222b`)
- [x] **STEP 1.4: Comparative Verification Benchmark (Greedy vs. Hungarian)** (`1fb222b`)

---

## Phase 1.5: Clean Code & SOLID Overhaul `[COMPLETED]`

- [x] **STEP CC.1: Weapon Polymorphism & Exception Safety (`weapons.py`) [LSP & Clean Code]**
  - **Files:** `weapons.py`, `vehicle.py`
  - **Result:** Unified `fire(target=None) -> bool` signature across base and derived weapons. Removed bare `except:` blocks and Portuguese print statements. Full polymorphic unit test passed.

- [x] **STEP CC.2: State Machine Consolidation (DRY & SRP in `state_machine.py`)**
  - **Files:** `state_machine.py`
  - **Result:** Consolidated 4 duplicate 45-line attack classes (`AttackLeaderState`, `AttackLoyalWingmanState`, `AttackProtectedAreaState`, `AttackKamikazeState`) into a single extensible `AttackTargetState(target_type)`. Removed dead code blocks.

- [x] **STEP CC.3: Decouple Kinematics from Rendering & Dead Code Removal in `vehicle.py` [SRP & ISP]**
  - **Files:** `vehicle.py`
  - **Result:** Purged dead commented-out tuning blocks (`# kp = 0.0024`, `# kv = 800`, etc.). Streamlined PD `arrive()` controller. Explicit error handling.

- [x] **STEP CC.4: Nomenclature & Language Standardization (`decision_making.py`)**
  - **Files:** `decision_making.py`
  - **Result:** Standardized docstrings to formal English. Replaced academic Roomba references with MUM-T aerospace terminology. Cleaned up sequence execution returns.

- [x] **STEP CC.5: Complete Regression & Benchmarking Verification**
  - **Files:** `test_allocation.py`, `main.py`
  - **Result:** Headless parallel PSO (80 episodes in 5.3s), GUI loop (60 frames), and Hungarian target allocation tests all passed with zero errors.

---

## Phase 2: Dynamic Formations & Tactical Geometries `[NEXT]`

- [ ] **STEP 2.1: Formation Geometry Engine in `LeadingDrone` (Strategy Pattern)**
- [ ] **STEP 2.2: Hotkey & HUD Formation Control**
- [ ] **STEP 2.3: Smooth Re-formation Steering & Anti-Collision**

---

## Phase 3: Interactive Real-Time Dashboard (`dashboard.py`)

- [ ] **STEP 3.1: Thread-Safe Inter-Process Communication (IPC)**
- [ ] **STEP 3.2: Tkinter Parameter Dashboard with Live Sliders**
- [ ] **STEP 3.3: Embedded Real-Time Telemetry & Matplotlib Graphs**

---

## Phase 4: Dynamic Ballistics & Kamikaze Evasion

- [ ] **STEP 4.1: Projectile Kinematics & Visual Tracers**
- [ ] **STEP 4.2: Kamikaze Evasive Steering & Jinking**

---

## Phase 5: Monte Carlo Sweeps & Publication Assets (PhD/Paper)

- [ ] **STEP 5.1: Automated Matrix Sweep Orchestrator (`sweep_runner.py`)**
- [ ] **STEP 5.2: Publication Figure Generator (`plot_generator.py`)**
- [ ] **STEP 5.3: Automated LaTeX Summary Table Generator**
