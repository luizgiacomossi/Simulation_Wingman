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
    Asynchronous Tactical Commander connecting the simulation to local SLM/LLM inference.
    Executes in a separate daemon thread to guarantee zero frame drops in 60 FPS Pygame physics.
    """
    persistent_enabled: bool = ("--llm" in sys.argv or "--ai" in sys.argv)

    def __init__(self,
                 api_url: str = "http://127.0.0.1:1234/v1/chat/completions",
                 model_name: str = "qwen/qwen3.5-9b",
                 decision_interval: float = 5.0,
                 timeout: float = 25.0):
        self.api_url = api_url
        self.model_name = model_name
        self.decision_interval = decision_interval
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

    def toggle(self) -> bool:
        """Toggles LLM Commander active state and preserves across episode resets."""
        self.enabled = not self.enabled
        LLMTacticalCommander.persistent_enabled = self.enabled
        print(f"[LLM Commander] State changed: {'ENABLED' if self.enabled else 'DISABLED'}")
        return self.enabled

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
                worker = threading.Thread(
                    target=self._async_query_llm,
                    args=(snapshot,),
                    daemon=True,
                    name="LLM-Commander-Worker"
                )
                worker.start()

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
        return {
            "enabled": self.enabled,
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
