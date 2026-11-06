import urllib.request
import json
import time
import math
import csv
import os

URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = "qwen/qwen3.5-9b"

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

scenarios = [
    {
        "id": 1,
        "name": "Massive Frontal Wave Attack",
        "state": {
            "leader": {"pos": [960, 540], "heading_deg": 90, "speed": 2.0},
            "protected_area": {"pos": [960, 650], "radius": 100, "status": "SECURE"},
            "num_wingmen_alive": 8,
            "threats_detected": [
                {"id": "K1", "pos": [960, 150], "speed": 3.0, "bearing_deg": 0, "target": "PROTECTED_AREA"},
                {"id": "K2", "pos": [920, 140], "speed": 3.2, "bearing_deg": 0, "target": "LEADER"},
                {"id": "K3", "pos": [1000, 160], "speed": 2.9, "bearing_deg": 0, "target": "PROTECTED_AREA"},
                {"id": "K4", "pos": [960, 100], "speed": 3.6, "bearing_deg": 0, "target": "LEADER"}
            ],
            "threat_summary": "4 hostile kamikaze UAVs descending in a coordinated linear wave from the NORTH."
        },
        "evaluation_criteria": {
            "optimal_formations": ["WALL", "WEDGE"],
            "interceptor_min": 5,
            "priority_target": "K4", # Closest and fastest (speed 3.6, y=100)
            "must_protect": "LEADER",
            "recommended_leader_action": ["EVADE_RETREAT", "HOLD_DEFENSIVE"]
        }
    },
    {
        "id": 2,
        "name": "360-Degree Omnidirectional Pincer Attack",
        "state": {
            "leader": {"pos": [960, 540], "heading_deg": 0, "speed": 1.0},
            "protected_area": {"pos": [960, 540], "radius": 100, "status": "COINCIDENT_WITH_LEADER"},
            "num_wingmen_alive": 8,
            "threats_detected": [
                {"id": "K_NORTH", "pos": [960, 180], "speed": 3.0, "bearing_deg": 0, "target": "LEADER"},
                {"id": "K_SOUTH", "pos": [960, 900], "speed": 3.0, "bearing_deg": 180, "target": "LEADER"},
                {"id": "K_EAST", "pos": [1320, 540], "speed": 3.0, "bearing_deg": 90, "target": "LEADER"},
                {"id": "K_WEST", "pos": [600, 540], "speed": 3.0, "bearing_deg": 270, "target": "LEADER"}
            ],
            "threat_summary": "Symmetrical 4-axis pincer assault closing in simultaneously from all cardinal directions."
        },
        "evaluation_criteria": {
            "optimal_formations": ["CIRCLE"],
            "interceptor_min": 4,
            "priority_target": ["K_NORTH", "K_SOUTH", "K_EAST", "K_WEST"],
            "must_protect": "LEADER",
            "recommended_leader_action": ["HOLD_DEFENSIVE", "ORBIT_BASE"]
        }
    },
    {
        "id": 3,
        "name": "Critical Base Penetration (Protected Area Breach)",
        "state": {
            "leader": {"pos": [1200, 400], "heading_deg": 45, "speed": 2.0},
            "protected_area": {"pos": [500, 700], "radius": 80, "status": "UNDER_IMMINENT_THREAT"},
            "num_wingmen_alive": 7,
            "threats_detected": [
                {"id": "K_BREACH", "pos": [540, 640], "speed": 4.0, "dist_to_protected_area": 98, "target": "PROTECTED_AREA"},
                {"id": "K_DISTANT", "pos": [1400, 300], "speed": 2.2, "dist_to_protected_area": 980, "target": "LEADER"}
            ],
            "threat_summary": "K_BREACH has penetrated outer defensive ring and is 98m from detonating on the Protected Base."
        },
        "evaluation_criteria": {
            "optimal_formations": ["WALL", "CIRCLE", "WEDGE"],
            "interceptor_min": 3,
            "priority_target": "K_BREACH",
            "must_protect": "PROTECTED_AREA",
            "recommended_leader_action": ["EVADE_RETREAT", "HOLD_DEFENSIVE"]
        }
    },
    {
        "id": 4,
        "name": "High-Speed Lateral Flank Ambush",
        "state": {
            "leader": {"pos": [960, 540], "heading_deg": 0, "speed": 2.5}, # Moving North
            "protected_area": {"pos": [960, 750], "radius": 100, "status": "SECURE"},
            "num_wingmen_alive": 8,
            "threats_detected": [
                {"id": "K_FLANK_LEAD", "pos": [1400, 480], "speed": 3.8, "bearing_deg": 75, "target": "LEADER"},
                {"id": "K_FLANK_TRAIL", "pos": [1460, 580], "speed": 3.5, "bearing_deg": 85, "target": "PROTECTED_AREA"}
            ],
            "threat_summary": "Fast-attack flank swarm attacking starboard (EAST) while MUM-T flight transits North."
        },
        "evaluation_criteria": {
            "optimal_formations": ["ECHELON", "WALL"],
            "interceptor_min": 5,
            "priority_target": "K_FLANK_LEAD",
            "must_protect": "LEADER",
            "recommended_leader_action": ["EVADE_RETREAT", "HOLD_DEFENSIVE"]
        }
    },
    {
        "id": 5,
        "name": "Resource-Constrained Attrition Defense",
        "state": {
            "leader": {"pos": [960, 540], "heading_deg": 90, "speed": 1.5},
            "protected_area": {"pos": [960, 680], "radius": 100, "status": "CRITICAL_VULNERABILITY"},
            "num_wingmen_alive": 3, # Severe attrition!
            "threats_detected": [
                {"id": "K_SWARM_1", "pos": [960, 220], "speed": 3.0, "target": "PROTECTED_AREA"},
                {"id": "K_SWARM_2", "pos": [880, 240], "speed": 2.8, "target": "PROTECTED_AREA"},
                {"id": "K_SWARM_3", "pos": [1040, 230], "speed": 2.9, "target": "PROTECTED_AREA"},
                {"id": "K_SWARM_4", "pos": [750, 400], "speed": 2.5, "target": "LEADER"},
                {"id": "K_SWARM_5", "pos": [1170, 400], "speed": 2.5, "target": "LEADER"}
            ],
            "threat_summary": "Outnumbered 3 wingmen vs 5 kamikazes. High risk of total saturation."
        },
        "evaluation_criteria": {
            "optimal_formations": ["WALL", "CIRCLE"],
            "interceptor_min": 2,
            "priority_target": ["K_SWARM_1", "K_SWARM_2", "K_SWARM_3"], # Base protection
            "must_protect": "PROTECTED_AREA",
            "recommended_leader_action": ["ORBIT_BASE", "EVADE_RETREAT"]
        }
    },
    {
        "id": 6,
        "name": "Tactical Decoy & Divergence Strike",
        "state": {
            "leader": {"pos": [960, 540], "heading_deg": 0, "speed": 2.0},
            "protected_area": {"pos": [960, 800], "radius": 90, "status": "SECURE"},
            "num_wingmen_alive": 8,
            "threats_detected": [
                {"id": "K_DECOY", "pos": [300, 300], "speed": 1.2, "bearing_deg": 315, "target": "EMPTY_AIRSPACE"}, # Low speed, far decoy
                {"id": "K_STRIKE_1", "pos": [940, 300], "speed": 3.8, "bearing_deg": 0, "target": "PROTECTED_AREA"},
                {"id": "K_STRIKE_2", "pos": [980, 290], "speed": 3.9, "bearing_deg": 0, "target": "PROTECTED_AREA"}
            ],
            "threat_summary": "K_DECOY attempting to lure interceptors away to Northwest, while main strike dives on the Base."
        },
        "evaluation_criteria": {
            "optimal_formations": ["WALL", "WEDGE"],
            "interceptor_min": 5,
            "priority_target": ["K_STRIKE_1", "K_STRIKE_2"], # Must ignore or deprioritize decoy
            "must_protect": "PROTECTED_AREA",
            "recommended_leader_action": ["HOLD_DEFENSIVE", "ORBIT_BASE"]
        }
    }
]

def query_qwen(prompt):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": "</think>\n{"}
        ],
        "temperature": 0.1,
        "max_tokens": 500
    }
    req = urllib.request.Request(URL, data=json.dumps(payload).encode('utf-8'), headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            res_data = json.loads(r.read().decode('utf-8'))
            elapsed = time.time() - t0
            usage = res_data.get("usage", {})
            raw_content = "{" + res_data["choices"][0]["message"].get("content", "")
            return raw_content, elapsed, usage
    except Exception as e:
        return f"Error: {e}", 0, {}

print("================================================================================")
print("     MUM-T AUTONOMOUS SWARM LEADER: COMPREHENSIVE TACTICAL BENCHMARK SUITE      ")
print("================================================================================")
print(f"Target Model: {MODEL} via LM Studio Local Inference")
print(f"Airspace Context: Loyal Wingman Escort Swarm & Strategic Asset Defense\n")

benchmark_records = []

for sc in scenarios:
    print(f">> Executing Scenario {sc['id']}: {sc['name']}...")
    prompt_text = f"CURRENT TACTICAL TELEMETRY:\n{json.dumps(sc['state'], indent=2)}\n\nCompute the optimal immediate swarm command decision."
    
    raw_str, latency, usage = query_qwen(prompt_text)
    
    # JSON Parsing
    json_valid = False
    decision = {}
    clean_str = raw_str.strip()
    if clean_str.endswith("```"):
        clean_str = clean_str[:-3].strip()
    
    try:
        decision = json.loads(clean_str)
        json_valid = True
    except Exception:
        s_idx = clean_str.find("{")
        e_idx = clean_str.rfind("}")
        if s_idx != -1 and e_idx != -1:
            try:
                decision = json.loads(clean_str[s_idx:e_idx+1])
                json_valid = True
            except:
                pass

    # Token Metrics
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)
    tps = round(completion_tokens / latency, 2) if latency > 0 else 0.0

    # Verification & Hallucination Detection
    valid_threat_ids = [t["id"] for t in sc["state"]["threats_detected"]]
    reported_priorities = decision.get("target_priority_order", [])
    hallucinated_ids = [tid for tid in reported_priorities if tid not in valid_threat_ids]
    hallucination_detected = len(hallucinated_ids) > 0

    # Tactical Scoring Engine (0-100 total)
    formation_score = 0
    allocation_score = 0
    priority_score = 0
    leader_action_score = 0
    crit = sc["evaluation_criteria"]

    if json_valid:
        # 1. Formation Appropriateness (25 pts)
        sel_formation = decision.get("selected_formation", "").upper()
        if sel_formation in crit.get("optimal_formations", []):
            formation_score = 25
        elif sel_formation in ["WALL", "CIRCLE", "ECHELON", "WEDGE"]:
            formation_score = 12

        # 2. Tactical Role Allocation (25 pts)
        n_inter = decision.get("num_interceptors", 0)
        n_escort = decision.get("num_close_escorts", 0)
        total_wingmen = sc["state"]["num_wingmen_alive"]
        min_inter = crit.get("interceptor_min", 1)
        
        # Check conservation of agents
        if (n_inter + n_escort) == total_wingmen:
            allocation_score += 10
        elif (n_inter + n_escort) <= total_wingmen:
            allocation_score += 5
            
        if n_inter >= min_inter:
            allocation_score += 15
        elif n_inter > 0:
            allocation_score += 8

        # 3. Threat Prioritization Accuracy (30 pts)
        top_p = reported_priorities[0] if reported_priorities else None
        target_rule = crit.get("priority_target")
        if isinstance(target_rule, list):
            if top_p in target_rule:
                priority_score = 30
            elif any(p in target_rule for p in reported_priorities[:2]):
                priority_score = 20
        else:
            if top_p == target_rule:
                priority_score = 30
            elif target_rule in reported_priorities[:2]:
                priority_score = 15

        # Penalize if decoy was prioritized in Scenario 6
        if sc["id"] == 6 and top_p == "K_DECOY":
            priority_score = 0

        # 4. Leader Survival Action (20 pts)
        sel_action = decision.get("leader_action", "")
        if sel_action in crit.get("recommended_leader_action", []):
            leader_action_score = 20
        elif sel_action in ["HOLD_DEFENSIVE", "ENGAGE_FORWARD", "EVADE_RETREAT", "ORBIT_BASE"]:
            leader_action_score = 10

    total_tactical_score = formation_score + allocation_score + priority_score + leader_action_score

    record = {
        "scenario_id": sc["id"],
        "scenario_name": sc["name"],
        "decision_latency_sec": round(latency, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "tokens_per_second": tps,
        "json_valid": json_valid,
        "selected_formation": decision.get("selected_formation", "N/A"),
        "formation_score": formation_score,
        "interceptors_assigned": decision.get("num_interceptors", 0),
        "escorts_assigned": decision.get("num_close_escorts", 0),
        "allocation_score": allocation_score,
        "top_priority_target": reported_priorities[0] if reported_priorities else "N/A",
        "priority_score": priority_score,
        "leader_action": decision.get("leader_action", "N/A"),
        "leader_action_score": leader_action_score,
        "total_tactical_score": total_tactical_score,
        "hallucinated_ids": hallucinated_ids,
        "tactical_rationale": decision.get("tactical_rationale", "N/A")
    }
    benchmark_records.append(record)

    print(f"   [DONE] Latency: {latency:.2f}s | TPS: {tps} | Tactical Score: {total_tactical_score}/100")
    print(f"          Formation: {record['selected_formation']} | Interceptors: {record['interceptors_assigned']} | Top Target: {record['top_priority_target']}")
    print(f"          Action: {record['leader_action']}")
    print(f"          Rationale: {record['tactical_rationale']}\n")

# Compute Aggregate Statistics
avg_latency = round(sum(r["decision_latency_sec"] for r in benchmark_records) / len(benchmark_records), 2)
avg_tps = round(sum(r["tokens_per_second"] for r in benchmark_records) / len(benchmark_records), 2)
avg_score = round(sum(r["total_tactical_score"] for r in benchmark_records) / len(benchmark_records), 2)
json_success_rate = round((sum(1 for r in benchmark_records if r["json_valid"]) / len(benchmark_records)) * 100, 1)
total_tokens_consumed = sum(r["total_tokens"] for r in benchmark_records)
hallucination_count = sum(len(r["hallucinated_ids"]) for r in benchmark_records)

summary_dict = {
    "aggregate_metrics": {
        "model": MODEL,
        "scenarios_evaluated": len(benchmark_records),
        "average_decision_latency_sec": avg_latency,
        "average_throughput_tps": avg_tps,
        "mean_tactical_score_percent": avg_score,
        "json_schema_compliance_percent": json_success_rate,
        "total_tokens_consumed": total_tokens_consumed,
        "total_entity_hallucinations": hallucination_count
    },
    "detailed_records": benchmark_records
}

# Export JSON
json_path = "/Users/lgr03/.gemini/antigravity/brain/958e6087-d3af-4f39-b175-b4b246997eec/scratch/tactical_benchmark_full.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(summary_dict, f, ensure_ascii=False, indent=2)

# Export CSV
csv_path = "/Users/lgr03/.gemini/antigravity/brain/958e6087-d3af-4f39-b175-b4b246997eec/scratch/tactical_benchmark_metrics.csv"
fieldnames = [
    "scenario_id", "scenario_name", "decision_latency_sec", "tokens_per_second",
    "prompt_tokens", "completion_tokens", "total_tokens", "json_valid",
    "selected_formation", "formation_score", "interceptors_assigned", "escorts_assigned",
    "allocation_score", "top_priority_target", "priority_score",
    "leader_action", "leader_action_score", "total_tactical_score"
]

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in benchmark_records:
        writer.writerow(r)

print("================================================================================")
print(f"BENCHMARK COMPLETED SUCCESSFULLY! Records saved to:")
print(f"JSON: {json_path}")
print(f"CSV:  {csv_path}")
print(f"Summary: Avg Latency = {avg_latency}s | Avg Score = {avg_score}/100 | TPS = {avg_tps}")
print("================================================================================")
