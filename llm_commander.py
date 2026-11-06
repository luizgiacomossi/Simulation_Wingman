"""
Autonomous LLM Tactical Mission Commander for MUM-T Air Defense.
Provides non-blocking asynchronous macro-tactical decision making for the Leading Drone
using local Small Language Models (e.g. Qwen 3.5 9B on Apple Silicon / LM Studio).
Decoupled architecture: operates via background thread workers and broadcasts commands
over the decentralized Tactical Datalink Bus (MessageManager).
"""

import sys
import json
import time
import math
import threading
import urllib.request
from typing import Dict, List, Optional, Any
from pygame.math import Vector2

from constants import *
from message_manager import TacticalMessage, MessageTopic


SYSTEM_PROMPT = """You are the Autonomous Mission Commander and Tactical Air Defense AI aboard the Leading Aircraft in a Manned-Unmanned Teaming (MUM-T) airspace operation.
You command an escort swarm of autonomous Loyal Wingman UAVs to defend both the Flight Lead (Leader) and a high-value strategic Protected Area (Ground Base) against saturation hostile Kamikaze UAV attacks.

Available Formations:
- "WALL": Linear barrier perpendicular to threat vector. Optimal against single-direction frontal waves.
- "CIRCLE": Equidistant radial perimeter ring. Optimal against 360-degree omnidirectional saturation attacks.
- "ECHELON": Stepped diagonal formation. Optimal against lateral flank attacks and asymmetric threats.
- "WEDGE": Symmetrical swept-back V-formation. Optimal for directional penetration, aggressive interception, and corridor clearing.

Available Tactical Roles for Wingmen:
- "CLOSE_ESCORT": Wingmen tethered to the defensive geometry surrounding the Leader and Protected Area.
- "INTERCEPTOR": Wingmen dispatched ahead to hunt and destroy incoming kamikaze threats with kinetic and directed-energy weapons.

Leader Actions:
- "HOLD_DEFENSIVE": Maintain position/orbit while wingmen engage.
- "ENGAGE_FORWARD": Push flight forward to intercept distant threats.
- "EVADE_RETREAT": Disengage and reposition away from incoming high-velocity collision vectors.
- "ORBIT_BASE": Circle tightly around the Protected Area to reinforce perimeter coverage.

You must respond STRICTLY with valid JSON following this schema:
{
  "selected_formation": "WALL" | "CIRCLE" | "ECHELON" | "WEDGE",
  "num_interceptors": int,
  "num_close_escorts": int,
  "target_priority_order": ["ID1", "ID2", ...],
  "leader_action": "HOLD_DEFENSIVE" | "ENGAGE_FORWARD" | "EVADE_RETREAT" | "ORBIT_BASE",
  "tactical_rationale": "Concise military doctrine justification in 1-2 sentences."
}
Do not output conversational filler. Provide only the JSON object."""


class LLMTacticalCommander:
    """
    Asynchronous Tactical Commander connecting the simulation to local AI inference.
    Supports dual execution engines:
    1. 'laya': Non-autoregressive System 1 decision model (Convai Laya) on Apple Silicon MPS (~24ms).
    2. 'qwen': Autoregressive System 2 generative SLM (Qwen 3.5 9B) via LM Studio (~5s).
    Executes in a separate daemon thread to guarantee zero frame drops in 60 FPS Pygame physics.
    """
    persistent_enabled: bool = ("--llm" in sys.argv or "--ai" in sys.argv or "--laya" in sys.argv)
    persistent_engine: str = "qwen" if "--llm" in sys.argv else "laya"

    def __init__(self,
                 engine: Optional[str] = None,
                 api_url: str = "http://127.0.0.1:1234/v1/chat/completions",
                 model_name: str = "qwen/qwen3.5-9b",
                 decision_interval: Optional[float] = None,
                 timeout: float = 25.0):
        self.engine = engine if engine else LLMTacticalCommander.persistent_engine
        self.api_url = api_url
        self.model_name = model_name
        self.decision_interval = decision_interval if decision_interval is not None else (1.0 if self.engine == "laya" else 5.0)
        self.timeout = timeout

        self.enabled = LLMTacticalCommander.persistent_enabled
        self.is_request_in_flight = False
        self.last_decision_time = -999.0
        self.last_decision: Optional[Dict[str, Any]] = None
        self.last_latency: float = 0.0
        self.total_decisions: int = 0
        self.last_error: Optional[str] = None

        self._lock = threading.Lock()
        self._pending_decision: Optional[Dict[str, Any]] = None
        self._laya_agent = None

    def toggle(self) -> bool:
        """Toggles AI Commander active state and preserves across episode resets."""
        self.enabled = not self.enabled
        LLMTacticalCommander.persistent_enabled = self.enabled
        print(f"[AI Commander] State changed: {'ENABLED' if self.enabled else 'DISABLED'} [Engine: {self.engine.upper()}]")
        return self.enabled

    def switch_engine(self, engine: Optional[str] = None) -> str:
        """Switches between 'laya' (24ms reflex) and 'qwen' (5s generative)."""
        if engine in ("laya", "qwen"):
            self.engine = engine
        else:
            self.engine = "qwen" if self.engine == "laya" else "laya"

        LLMTacticalCommander.persistent_engine = self.engine
        self.decision_interval = 1.0 if self.engine == "laya" else 5.0
        print(f"[AI Commander] Switched engine to: {self.engine.upper()} (Interval: {self.decision_interval}s)")
        return self.engine

    def build_telemetry_snapshot(self, simulation: Any) -> Dict[str, Any]:
        """Constructs an anonymized, standardized tactical state JSON for the LLM."""
        sm = simulation.swarm_manager
        leader = sm.leadingdrone
        base = sm.protected_area

        leader_pos = [round(leader.location.x, 1), round(leader.location.y, 1)] if leader else [0, 0]
        leader_heading = 0.0
        if leader and hasattr(leader, 'velocity') and leader.velocity.magnitude() > 0.01:
            leader_heading = round(math.degrees(math.atan2(leader.velocity.y, leader.velocity.x)), 1)

        base_pos = [round(base.pos.x, 1), round(base.pos.y, 1)] if base and hasattr(base, 'pos') else [0, 0]
        base_life = getattr(base, 'life', 100)
        base_active = base.is_active() if base and hasattr(base, 'is_active') else True

        threats = []
        for i, k in enumerate(sm.kamikazes):
            if getattr(k, 'destroyed', False) or getattr(k, 'explode', False):
                continue
            k_id = getattr(k, 'agent_id', f"K_{i+1}")
            k_pos = [round(k.location.x, 1), round(k.location.y, 1)]
            k_speed = round(k.velocity.magnitude(), 2) if hasattr(k, 'velocity') else 2.0
            
            # Approximate bearing from leader
            bearing = 0.0
            if leader:
                rel = k.location - leader.location
                bearing = round((math.degrees(math.atan2(rel.y, rel.x)) + 360) % 360, 1)

            threats.append({
                "id": str(k_id),
                "pos": k_pos,
                "speed": k_speed,
                "bearing_deg": bearing,
                "target": "PROTECTED_AREA" if (i % 2 == 0) else "LEADER"
            })

        # Loyal Wingmen individual telemetry
        wingmen_data = []
        for i, w in enumerate(sm.swarm):
            w_pos = [round(w.location.x, 1), round(w.location.y, 1)]
            w_speed = round(w.velocity.magnitude(), 2) if hasattr(w, 'velocity') else 0.0
            w_vap = w.vaporizer_gun.get_ammo_available() if hasattr(w, 'vaporizer_gun') else 0
            w_frz = w.freezing_gun.get_ammo_available() if hasattr(w, 'freezing_gun') else 0
            wingmen_data.append({
                "id": f"LW_{i+1:02d}",
                "pos": w_pos,
                "speed": w_speed,
                "role": getattr(w, 'tactical_role', 'INTERCEPTOR'),
                "ammo_vaporizer": w_vap,
                "ammo_cryo": w_frz
            })

        return {
            "leader": {
                "pos": leader_pos,
                "heading_deg": leader_heading,
                "speed": round(leader.velocity.magnitude(), 2) if leader else 0.0
            },
            "protected_area": {
                "pos": base_pos,
                "radius": getattr(base, 'radius', 100),
                "life": base_life,
                "status": "SECURE" if base_active and base_life > 50 else "UNDER_THREAT"
            },
            "num_wingmen_alive": len(sm.swarm),
            "loyal_wingmen": wingmen_data,
            "threats_detected": threats,
            "simulation_time_sec": round(sm.simulation_time, 2)
        }

    def update(self, current_time: float, simulation: Any) -> None:
        """
        Main non-blocking update hook called inside simulation.py run_simulation().
        Dispatches async requests and applies delivered decisions.
        """
        # 1. Check if a decision was returned from the worker thread
        with self._lock:
            if self._pending_decision is not None:
                decision = self._pending_decision
                self._pending_decision = None
                self._apply_decision(decision, simulation)

        if not self.enabled:
            return

        # 2. Check if it is time to request a new macro tactical decision
        if (current_time - self.last_decision_time >= self.decision_interval) and not self.is_request_in_flight:
            # Only trigger if threats exist
            if len(simulation.swarm_manager.kamikazes) > 0:
                self.is_request_in_flight = True
                self.last_decision_time = current_time
                snapshot = self.build_telemetry_snapshot(simulation)
                target_func = self._async_query_laya if self.engine == "laya" else self._async_query_llm
                worker = threading.Thread(
                    target=target_func,
                    args=(snapshot,),
                    daemon=True,
                    name=f"AI-Commander-{self.engine.title()}-Worker"
                )
                worker.start()

    def _get_laya_agent(self):
        """Lazy-loads Convai Laya model onto Apple Silicon MPS or CPU."""
        if self._laya_agent is None:
            import laya
            import torch
            device = 'mps' if torch.backends.mps.is_available() else 'cpu'
            print(f"[Laya Commander] Initializing Convai Laya decision engine on {device.upper()}...")
            self._laya_agent = laya.load('convaiinnovations/laya', device=device)
            print("[Laya Commander] Laya System-1 decision agent ready for sub-50ms inference.")
        return self._laya_agent

    def _async_query_laya(self, snapshot: Dict[str, Any]) -> None:
        """Worker thread executing sub-50ms non-autoregressive decision inference via Laya."""
        try:
            import laya
            agent = self._get_laya_agent()
            t0 = time.time()
            state_text = (
                f"Tactical Air Defense Status: Base integrity {snapshot['protected_area']['life']}%, "
                f"status {snapshot['protected_area']['status']}. "
                f"Wingmen operational: {snapshot['num_wingmen_alive']}. "
                f"Threat radar tracks {len(snapshot['threats_detected'])} inbound hostiles."
            )
            for t in snapshot['threats_detected'][:4]:
                state_text += f" Target {t['id']}: bearing {t.get('bearing_deg', 0)} deg, speed {t.get('speed', 0)} px/f."

            questions = {
                "selected_formation": {
                    "type": "choice",
                    "instructions": "Which swarm tactical formation best defends against incoming threats?",
                    "criteria": {
                        "WALL": "Linear defensive screen perpendicular to hostile ingress corridor.",
                        "CIRCLE": "Radial perimeter defense ring around protected base.",
                        "ECHELON": "Staggered diagonal formation to sweep flank attacks.",
                        "WEDGE": "Spearhead formation for aggressive frontal interception."
                    }
                },
                "leader_action": {
                    "type": "choice",
                    "instructions": "What maneuver should the Flight Lead execute?",
                    "criteria": {
                        "HOLD_DEFENSIVE": "Maintain stand-off orbit while wingmen engage.",
                        "ENGAGE_FORWARD": "Advance forward escorted by wingmen.",
                        "EVADE_RETREAT": "Reposition away from incoming collision vectors.",
                        "ORBIT_BASE": "Circle around the protected base."
                    }
                },
                "scramble_interceptors": {
                    "type": "noul",
                    "instructions": "Should wingmen be dispatched as interceptors rather than close escort?"
                },
                "threat_severity": {
                    "type": "score",
                    "instructions": "How critical is the immediate danger to mission assets?",
                    "criteria": [
                        "minimal: distant hostiles",
                        "low: outside defense zone",
                        "medium: converging towards assets",
                        "critical: penetrating inner defense zone"
                    ]
                }
            }

            res = laya.decide(agent, state_text, questions=questions)
            latency = round(time.time() - t0, 3)

            form = res.get("selected_formation", {}).get("choice", "WALL")
            action = res.get("leader_action", {}).get("choice", "HOLD_DEFENSIVE")
            scramble = res.get("scramble_interceptors", {}).get("action", {}).get("act_probability", 0) > 0.5
            severity = res.get("threat_severity", {}).get("score", 1.0)
            conf = res.get("selected_formation", {}).get("answer_confidence", 0.0)

            total_wingmen = snapshot["num_wingmen_alive"]
            num_int = min(len(snapshot["threats_detected"]), total_wingmen) if scramble else 0
            num_esc = total_wingmen - num_int
            priorities = [t["id"] for t in snapshot["threats_detected"]]

            decision = {
                "selected_formation": form,
                "leader_action": action,
                "num_interceptors": num_int,
                "num_close_escorts": num_esc,
                "target_priority_order": priorities,
                "tactical_rationale": f"Laya System-1 reflex [MPS {int(latency*1000)}ms]: {form} selected (conf {conf:.2f}). Threat level {severity:.1f}.",
                "_latency": latency,
                "_timestamp": time.time()
            }

            with self._lock:
                self._pending_decision = decision
                self.last_decision = decision
                self.last_latency = latency
                self.last_error = None
                self.total_decisions += 1
            print(f"[Laya Commander] Decision in {int(latency*1000)}ms: {form} | Action: {action} | Role: {num_int} INT / {num_esc} ESC")

        except Exception as e:
            with self._lock:
                self.last_error = str(e)
            print(f"[Laya Commander Error] Inference failed: {e}")
        finally:
            with self._lock:
                self.is_request_in_flight = False

    def _async_query_llm(self, snapshot: Dict[str, Any]) -> None:
        """Worker thread executing the HTTP inference request to the local SLM."""
        t0 = time.time()
        prompt_text = f"CURRENT TACTICAL TELEMETRY:\n{json.dumps(snapshot, indent=2)}\n\nCompute the optimal immediate swarm command decision."

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_text},
                {"role": "assistant", "content": "</think>\n{"}
            ],
            "temperature": 0.1,
            "max_tokens": 400
        }

        try:
            req = urllib.request.Request(
                self.api_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                latency = round(time.time() - t0, 2)
                raw_content = "{" + res_data["choices"][0]["message"].get("content", "")

                # Clean markdown fences
                clean = raw_content.strip()
                if clean.endswith("```"):
                    clean = clean[:-3].strip()

                parsed = None
                try:
                    parsed = json.loads(clean)
                except Exception:
                    s = clean.find("{")
                    e = clean.rfind("}")
                    if s != -1 and e != -1:
                        parsed = json.loads(clean[s:e+1])

                if parsed and isinstance(parsed, dict):
                    parsed["_latency"] = latency
                    parsed["_timestamp"] = time.time()
                    with self._lock:
                        self._pending_decision = parsed
                        self.last_latency = latency
                        self.last_error = None
                        self.total_decisions += 1
                    print(f"[LLM Commander] Decision received in {latency}s: {parsed.get('selected_formation')} | Priority: {parsed.get('target_priority_order', [None])[0]}")

        except Exception as e:
            with self._lock:
                self.last_error = str(e)
            print(f"[LLM Commander Error] Failed to query local model: {e}")

        finally:
            with self._lock:
                self.is_request_in_flight = False

    def _apply_decision(self, decision: Dict[str, Any], simulation: Any) -> None:
        """Applies the parsed directive directly onto the SwarmManager subsystems."""
        sm = simulation.swarm_manager
        self.last_decision = decision

        # 1. Reconfigure Formation Geometry via Strategy Pattern
        formation_name = str(decision.get("selected_formation", "CIRCLE")).upper()
        if formation_name in ("CIRCLE", "WEDGE", "WALL", "ECHELON"):
            sm.set_formation_strategy(formation_name)

        # 2. Divide Tactical Roles between Interceptors and Close Escorts
        num_interceptors = decision.get("num_interceptors", len(sm.swarm) // 2)
        if sm.swarm and len(sm.swarm) > 0:
            # Sort wingmen by distance to threats to allocate closest as interceptors
            if sm.kamikazes and len(sm.kamikazes) > 0:
                threat_center = sum((k.location for k in sm.kamikazes), Vector2(0, 0)) / len(sm.kamikazes)
                sorted_wingmen = sorted(sm.swarm, key=lambda w: w.location.distance_to(threat_center))
            else:
                sorted_wingmen = list(sm.swarm)

            for idx, wingman in enumerate(sorted_wingmen):
                if idx < num_interceptors:
                    wingman.tactical_role = "INTERCEPTOR"
                else:
                    wingman.tactical_role = "CLOSE_ESCORT"

        # 3. Inform Target Allocator about LLM Threat Priority
        priorities = decision.get("target_priority_order", [])
        if priorities and hasattr(sm, 'target_allocator'):
            # Bump priority weight for top targets
            sm.target_allocator.top_priority_ids = priorities

        # 4. Execute Flight Lead Evasive or Orbital Maneuver
        action = decision.get("leader_action", "HOLD_DEFENSIVE")
        leader = sm.leadingdrone
        base = sm.protected_area
        if leader:
            if action == "EVADE_RETREAT":
                # Compute evasion vector away from average threat location
                if sm.kamikazes and len(sm.kamikazes) > 0:
                    threat_center = sum((k.location for k in sm.kamikazes), Vector2(0, 0)) / len(sm.kamikazes)
                    evade_dir = (leader.location - threat_center)
                    if evade_dir.magnitude() > 0.01:
                        target_evade = leader.location + evade_dir.normalize() * 150.0
                        # Bound inside airspace
                        target_evade.x = max(100, min(WORLD_WIDTH - 100, target_evade.x))
                        target_evade.y = max(100, min(WORLD_HEIGHT - 100, target_evade.y))
                        leader.set_target(target_evade)

            elif action == "ORBIT_BASE" and base and hasattr(base, 'pos'):
                # Orbit around base perimeter
                orbit_target = base.pos + Vector2(120, 0).rotate(sm.simulation_time * 20.0)
                leader.set_target(orbit_target)

        # 5. Broadcast Tactical Notification on Datalink Bus
        if hasattr(sm, 'message_manager') and sm.message_manager is not None:
            sm.message_manager.broadcast(
                sender_id="LEADER",
                topic=MessageTopic.FORMATION_COMMAND,
                payload={
                    "formation": formation_name,
                    "num_interceptors": num_interceptors,
                    "priorities": priorities,
                    "action": action,
                    "rationale": decision.get("tactical_rationale", "")
                },
                current_time=sm.simulation_time
            )

    def get_hud_status(self) -> Dict[str, Any]:
        """Provides status summary for rendering onto the Glassmorphism HUD."""
        engine_label = "LAYA [MPS]" if self.engine == "laya" else "QWEN 3.5 [LM]"
        return {
            "enabled": self.enabled,
            "engine": self.engine,
            "engine_label": engine_label,
            "in_flight": self.is_request_in_flight,
            "is_thinking": self.is_request_in_flight,
            "last_formation": self.last_decision.get("selected_formation", "N/A") if self.last_decision else "N/A",
            "last_latency": self.last_latency,
            "last_target": self.last_decision.get("target_priority_order", ["N/A"])[0] if self.last_decision and self.last_decision.get("target_priority_order") else "N/A",
            "last_action": self.last_decision.get("leader_action", "N/A") if self.last_decision else "N/A",
            "num_interceptors": self.last_decision.get("num_interceptors", 0) if self.last_decision else 0,
            "num_close_escorts": self.last_decision.get("num_close_escorts", 0) if self.last_decision else 0,
            "rationale": self.last_decision.get("tactical_rationale", "") if self.last_decision else "",
            "total_decisions": self.total_decisions,
            "error": self.last_error
        }

    get_status_summary = get_hud_status
