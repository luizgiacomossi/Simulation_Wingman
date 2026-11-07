# Loyal Wingman Simulator (MUM-T) — Tactical & Scientific Improvements Checklist

This document catalogs tactical, behavioral, algorithmic, and architectural improvements for the `Simulation_Wingman` research platform, structured by research area for the PhD thesis and academic publications (IEEE/AIAA).

---

## 1. Loyal Wingman Tactical Behaviors & Coordination

- [x] **Anti-Overkill Fire Discipline via Datalink (Decentralized Coordination)**
  - **Concept:** When a wingman fires a lethal projectile at a threat, it broadcasts a `WEAPON_RELEASE` datalink message over the tactical bus.
  - **Mechanism:** Peers receive the notice, register the target into a local `engaged_threats` track table with a time-to-impact (ETA) timeout, and suppress redundant fire (*Shoot-Look-Shoot* doctrine).
  - **Opportunistic Retargeting:** If the primary target is already engaged, the wingman diverts fire to the next closest unengaged threat.
  - **Metric Impact:** Reduces shots-to-kill ratio ($S/K$) from ~2.8 down to ~1.1, tripling effective swarm magazine endurance.
  - **Status:** Completed and verified (`test_anti_overkill.py`).

- [x] **Return-to-Base (RTB) Munition Replenishment**
  - **Concept:** Wingmen in Winchester state (0 cartridges) return to the Protected Area base pad, rearm for 3.0 seconds, and return to formation.
  - **Visualization:** Technical radial progress HUD with pulsing halo, 360° fill arc, and animated munition pips.
  - **Status:** Completed and enabled by default (`test_rtb_logistics.py`).

- [x] **Winchester Sacrificial Ramming (Kinetic Interception)**
  - **Concept:** When completely out of ammo, if a hostile breaches the critical inner defense ring of the Leader or Base, the wingman executes a sacrificial body-block intercept.
  - **Status:** Completed and verified (`test_sacrificial_ramming.py`).

- [ ] **Tethering & Anti-Overextension Leash ($R_{\text{leash}}$)**
  - **Concept:** Prevent hostile decoys from baiting wingmen into the map corners.
  - **Mechanism:** If distance from the Leader exceeds $R_{\text{leash}}$ (e.g., $450\text{px}$), the wingman aborts pursuit and falls back into escort formation.

- [ ] **Cooperative Stasis-to-Kill Sequencing (Cryo + Plasma Combo)**
  - **Concept:** Fast-moving kamikazes are hard to hit with unguided bolts.
  - **Mechanism:** Wingman A tags the threat with `Freezing` (slowing it by 60%), making it an easy target for Wingman B's high-speed lethal `Vaporizer` bolt.

---

## 2. Adversarial Hostile AI & Evasion (Step 4.2 & 4.3 Roadmap)

- [ ] **Kamikaze Evasive Jinking & Breakout Maneuvers**
  - **Concept:** Hostile drones sense incoming projectile trajectories and defensive lock-on.
  - **Mechanism:** Inject lateral sinusoidal oscillatory acceleration $\mathbf{a}_{\text{jink}} = A \sin(\omega t) \mathbf{n}_{\perp}$ and high-G breakout turns to defeat 1st-order lead computing.
  - **Metric Impact:** Forces the defense to adopt closer engagement or cryo-slowing tactics.

- [ ] **Coordinated Salvo & Pincer Strikes**
  - **Concept:** Kamikazes assemble outside the perimeter and strike simultaneously from diametrically opposed vectors (North & South).
  - **Metric Impact:** Stresses the SLM/Laya commander to split swarm escort and balance defense hemispheres.

- [ ] **Bait & Penetrator Decoy Tactics**
  - **Concept:** Heavy durable decoy drones attract interceptor focus while high-speed penetrators target the unprotected Leader.

---

## 3. Communication & Electronic Warfare (EW / Datalink)

- [ ] **Datalink Degradation & Packet Loss Modeling**
  - **Concept:** Evaluate swarm performance under contested EW environments ($0\% - 60\%$ packet loss in `MessageManager`).
  - **Mechanism:** Drones that miss `FORMATION_COMMAND` or `WEAPON_RELEASE` fall back to dead reckoning and autonomous local behavior trees.
  - **Paper Contribution:** *"MUM-T Swarm Resilience Under Contested Electronic Warfare Environments"*.

- [ ] **Decentralized Distributed Consensus (Leaderless Fallback)**
  - **Concept:** If the Leading Drone is destroyed or jammed, the wingmen elect an autonomous deputy flight lead to maintain formation.

---

## 4. SLM / LLM Commander Enhancements

- [ ] **Dynamic Rules of Engagement (ROE)**
  - **Concept:** Commander selects operational doctrine: `AGGRESSIVE_INTERCEPT` (standoff outer perimeter), `DEFENSIVE_PERIMETER` (close base escort), or `CONVOY_DEFENSE` (tight leader umbrella).

- [ ] **Explainable Tactical Rationale Logging**
  - **Concept:** SLM outputs natural-language military reasoning logged directly into HUD and experiment telemetry (e.g., *"North corridor compromised; shifting Wedge to Shield Base"*).

---

## 5. Automated Benchmarking & Paper Assets (Phase 5 Roadmap)

- [ ] **Monte Carlo Automated Matrix Sweeps (`sweep_runner.py`)**
  - **Concept:** Headless execution of 50-100 seeds across ablation configurations (`baseline`, `laya-movement`, `laya-formation`, `laya-full`).

- [ ] **Survival Curve Generator (Kaplan-Meier & CDF Plots)**
  - **Concept:** Publication-quality vector plots (PDF/SVG) for survival time, kill ratio, and ammo efficiency.

- [ ] **Automated LaTeX Summary Table Exporter**
  - **Concept:** Direct generation of IEEE/AIAA formatted `\begin{table}` snippets with mean, standard deviation, and ANOVA $p$-values.
