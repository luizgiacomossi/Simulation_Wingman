"""
Interactive Real-Time Dashboard (MUM-T Tactical C2 Workstation).
Phase 3 of the Loyal Wingman Research Platform:
- Multiprocessing Queue-based IPC for non-blocking 60 FPS simulation.
- Real-time parameter sliders (Chase Distance, Formation Distance, Speed).
- Embedded live Matplotlib telemetry canvas (Base HP, Swarm Ammo, Threat Density).
- Operator Co-Pilot Console for natural language and tactical command dispatch.
"""

import sys
import time
import multiprocessing as mp
from queue import Empty
import tkinter as tk
from tkinter import ttk, scrolledtext
import numpy as np

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt


class TacticalDashboardApp:
    """
    Tkinter-based C2 Dashboard running in an independent OS process.
    Communicates with Pygame simulation via thread-safe multiprocessing Queues.
    """
    def __init__(self, root: tk.Tk, telemetry_queue: mp.Queue, command_queue: mp.Queue):
        self.root = root
        self.telemetry_queue = telemetry_queue
        self.command_queue = command_queue

        self.root.title("MUM-T TACTICAL C2 WORKSTATION & CO-PILOT")
        self.root.geometry("1180x760")
        self.root.configure(bg="#0F172A")  # Deep slate navy

        # Telemetry ring buffer for plotting (last 60 seconds at 10Hz)
        self.max_history = 600
        self.time_history = []
        self.base_hp_history = []
        self.ammo_history = []
        self.threats_history = []
        self.kills_history = []

        # Current state cache
        self.current_formation = "CIRCLE"
        self.ai_enabled = True
        self.rtb_enabled = True
        self.overkill_enabled = True

        self._setup_styles()
        self._build_layout()

        # Start periodic telemetry polling at 10Hz (100ms)
        self.root.after(100, self._poll_telemetry)

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Dark theme color tokens
        style.configure(".", background="#0F172A", foreground="#F8FAFC", font=("Helvetica", 10))
        style.configure("TFrame", background="#0F172A")
        style.configure("Card.TFrame", background="#1E293B", relief="flat")
        style.configure("TLabel", background="#0F172A", foreground="#F8FAFC", font=("Helvetica", 10))
        style.configure("Card.TLabel", background="#1E293B", foreground="#94A3B8", font=("Helvetica", 9))
        style.configure("Header.TLabel", background="#0F172A", foreground="#38BDF8", font=("Helvetica", 13, "bold"))
        style.configure("Value.TLabel", background="#1E293B", foreground="#F8FAFC", font=("Courier", 11, "bold"))

        # Button styling
        style.configure("Tactical.TButton", background="#334155", foreground="#38BDF8",
                        font=("Helvetica", 9, "bold"), borderwidth=1, padding=4)
        style.map("Tactical.TButton",
                  background=[("active", "#38BDF8"), ("pressed", "#0284C7")],
                  foreground=[("active", "#0F172A"), ("pressed", "#FFFFFF")])

        style.configure("Action.TButton", background="#0284C7", foreground="#FFFFFF",
                        font=("Helvetica", 9, "bold"), padding=4)
        style.map("Action.TButton",
                  background=[("active", "#38BDF8"), ("pressed", "#0369A1")])

    def _build_layout(self):
        # 1. Header Bar
        header = tk.Frame(self.root, bg="#0F172A", height=45)
        header.pack(side=tk.TOP, fill=tk.X, padx=16, pady=(12, 6))

        title = tk.Label(header, text="MUM-T TACTICAL C2 CO-PILOT WORKSTATION",
                         font=("Helvetica", 15, "bold"), fg="#38BDF8", bg="#0F172A")
        title.pack(side=tk.LEFT)

        self.status_lbl = tk.Label(header, text="STATUS: CONNECTED (60 FPS)",
                                   font=("Courier", 10, "bold"), fg="#4ADE80", bg="#0F172A")
        self.status_lbl.pack(side=tk.RIGHT)

        # 2. Main Body (Horizontal split: Left Controls / Right Plots)
        main_body = tk.Frame(self.root, bg="#0F172A")
        main_body.pack(fill=tk.BOTH, expand=True, padx=16, pady=6)

        # Left Column: Controls & Sliders
        left_col = tk.Frame(main_body, bg="#1E293B", width=340, padx=14, pady=14)
        left_col.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_col.pack_propagate(False)

        self._build_controls(left_col)

        # Right Column: Matplotlib Real-time Charts
        right_col = tk.Frame(main_body, bg="#1E293B", padx=8, pady=8)
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._build_charts(right_col)

        # 3. Bottom Row: Operator Dialogue & Audit Log
        bottom_bar = tk.Frame(self.root, bg="#1E293B", height=140, padx=12, pady=8)
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=(6, 12))
        bottom_bar.pack_propagate(False)

        self._build_terminal(bottom_bar)

    def _build_controls(self, parent):
        tk.Label(parent, text="TACTICAL CONTROLS", font=("Helvetica", 11, "bold"),
                 fg="#38BDF8", bg="#1E293B").pack(anchor="w", pady=(0, 10))

        # Formation Switcher
        tk.Label(parent, text="FORMATION STRATEGY", font=("Helvetica", 9, "bold"),
                 fg="#94A3B8", bg="#1E293B").pack(anchor="w")
        form_frame = tk.Frame(parent, bg="#1E293B")
        form_frame.pack(fill=tk.X, pady=(4, 12))

        for f_name in ["CIRCLE", "WEDGE", "WALL", "ECHELON"]:
            b = ttk.Button(form_frame, text=f_name, style="Tactical.TButton",
                           command=lambda fn=f_name: self._send_command("SET_FORMATION", {"formation": fn}))
            b.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        # Sliders
        # 1. Chase Distance
        tk.Label(parent, text="CHASE DISTANCE (px)", font=("Helvetica", 9, "bold"),
                 fg="#94A3B8", bg="#1E293B").pack(anchor="w")
        self.chase_val_lbl = tk.Label(parent, text="300 px", font=("Courier", 9), fg="#F8FAFC", bg="#1E293B")
        self.chase_val_lbl.pack(anchor="e")
        self.slider_chase = tk.Scale(parent, from_=50, to_=600, orient=tk.HORIZONTAL,
                                     bg="#1E293B", fg="#F8FAFC", highlightthickness=0,
                                     troughcolor="#334155", activebackground="#38BDF8",
                                     showvalue=False, command=self._on_chase_slider)
        self.slider_chase.set(300)
        self.slider_chase.pack(fill=tk.X, pady=(0, 10))

        # 2. Formation Spacing
        tk.Label(parent, text="FORMATION SPACING (px)", font=("Helvetica", 9, "bold"),
                 fg="#94A3B8", bg="#1E293B").pack(anchor="w")
        self.form_val_lbl = tk.Label(parent, text="100 px", font=("Courier", 9), fg="#F8FAFC", bg="#1E293B")
        self.form_val_lbl.pack(anchor="e")
        self.slider_form = tk.Scale(parent, from_=40, to_=250, orient=tk.HORIZONTAL,
                                    bg="#1E293B", fg="#F8FAFC", highlightthickness=0,
                                    troughcolor="#334155", activebackground="#38BDF8",
                                    showvalue=False, command=self._on_formation_slider)
        self.slider_form.set(100)
        self.slider_form.pack(fill=tk.X, pady=(0, 10))

        # 3. Simulation Speed
        tk.Label(parent, text="SIMULATION SPEED", font=("Helvetica", 9, "bold"),
                 fg="#94A3B8", bg="#1E293B").pack(anchor="w")
        spd_frame = tk.Frame(parent, bg="#1E293B")
        spd_frame.pack(fill=tk.X, pady=(4, 12))
        for spd in [1, 2, 4]:
            btn = ttk.Button(spd_frame, text=f"{spd}x", style="Tactical.TButton",
                             command=lambda s=spd: self._send_command("SET_SPEED", {"speed": s}))
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        # Tactical Toggles
        tk.Label(parent, text="TACTICAL DOCTRINE", font=("Helvetica", 9, "bold"),
                 fg="#94A3B8", bg="#1E293B").pack(anchor="w", pady=(4, 4))

        self.btn_rtb = ttk.Button(parent, text="RTB REARMING: [ENABLED]", style="Tactical.TButton",
                                  command=self._toggle_rtb)
        self.btn_rtb.pack(fill=tk.X, pady=2)

        self.btn_overkill = ttk.Button(parent, text="ANTI-OVERKILL: [ENABLED]", style="Tactical.TButton",
                                       command=self._toggle_overkill)
        self.btn_overkill.pack(fill=tk.X, pady=2)

        self.btn_ai = ttk.Button(parent, text="AI COMMANDER: [LAYA ON]", style="Tactical.TButton",
                                 command=self._toggle_ai)
        self.btn_ai.pack(fill=tk.X, pady=2)

        # Quick Actions
        tk.Label(parent, text="MANUAL SORTIE", font=("Helvetica", 9, "bold"),
                 fg="#94A3B8", bg="#1E293B").pack(anchor="w", pady=(10, 4))
        btn_kamikaze = ttk.Button(parent, text="+ SPAWN THREAT WAVE", style="Action.TButton",
                                  command=lambda: self._send_command("SPAWN_THREAT", {}))
        btn_kamikaze.pack(fill=tk.X, pady=2)

    def _build_charts(self, parent):
        # Matplotlib Dark Theme Figure
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(6.5, 4.2), sharex=True)
        self.fig.patch.set_facecolor("#1E293B")

        # Subplot 1: Base Life & Swarm Ammo
        self.ax1.set_facecolor("#0F172A")
        self.ax1.set_ylabel("Base HP / Ammo", color="#94A3B8", fontsize=8)
        self.ax1.tick_params(colors="#64748B", labelsize=8)
        self.ax1.grid(True, color="#334155", linestyle="--", alpha=0.5)

        self.line_base, = self.ax1.plot([], [], label="Base HP (%)", color="#F59E0B", lw=1.8)
        self.line_ammo, = self.ax1.plot([], [], label="Swarm Ammo", color="#38BDF8", lw=1.5)
        self.ax1.legend(loc="upper right", facecolor="#1E293B", edgecolor="#334155",
                        labelcolor="#F8FAFC", fontsize=7)

        # Subplot 2: Active Hostiles & Kills
        self.ax2.set_facecolor("#0F172A")
        self.ax2.set_xlabel("Sim Time (s)", color="#94A3B8", fontsize=8)
        self.ax2.set_ylabel("Hostiles / KIA", color="#94A3B8", fontsize=8)
        self.ax2.tick_params(colors="#64748B", labelsize=8)
        self.ax2.grid(True, color="#334155", linestyle="--", alpha=0.5)

        self.line_threats, = self.ax2.plot([], [], label="Active Threats", color="#EF4444", lw=1.5)
        self.line_kills, = self.ax2.plot([], [], label="Hostiles KIA", color="#4ADE80", lw=1.8)
        self.ax2.legend(loc="upper left", facecolor="#1E293B", edgecolor="#334155",
                        labelcolor="#F8FAFC", fontsize=7)

        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

    def _build_terminal(self, parent):
        top_row = tk.Frame(parent, bg="#1E293B")
        top_row.pack(fill=tk.X, pady=(0, 4))

        tk.Label(top_row, text="TACTICAL LOG & SLM CO-PILOT CONSOLE", font=("Helvetica", 9, "bold"),
                 fg="#38BDF8", bg="#1E293B").pack(side=tk.LEFT)

        # Command input
        input_row = tk.Frame(parent, bg="#1E293B")
        input_row.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 0))

        self.cmd_entry = tk.Entry(input_row, bg="#0F172A", fg="#F8FAFC", insertbackground="#38BDF8",
                                  relief="flat", font=("Courier", 10))
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=3)
        self.cmd_entry.bind("<Return>", lambda e: self._on_submit_cmd())

        btn_send = ttk.Button(input_row, text="EXECUTE", style="Action.TButton",
                              command=self._on_submit_cmd)
        btn_send.pack(side=tk.RIGHT)

        # Scrolled log
        self.log_txt = scrolledtext.ScrolledText(parent, bg="#0F172A", fg="#94A3B8",
                                                font=("Courier", 8), height=4, relief="flat")
        self.log_txt.pack(fill=tk.BOTH, expand=True)
        self.log_txt.insert(tk.END, "[SYSTEM] Tactical Datalink C2 bridge online. Listening for telemetry...\n")

    def _on_chase_slider(self, val):
        v = float(val)
        self.chase_val_lbl.config(text=f"{int(v)} px")
        self._send_command("SET_SLIDER", {"param": "distance_chase", "value": v})

    def _on_formation_slider(self, val):
        v = float(val)
        self.form_val_lbl.config(text=f"{int(v)} px")
        self._send_command("SET_SLIDER", {"param": "formation_distance", "value": v})

    def _toggle_rtb(self):
        self.rtb_enabled = not self.rtb_enabled
        st = "ENABLED" if self.rtb_enabled else "DISABLED"
        self.btn_rtb.config(text=f"RTB REARMING: [{st}]")
        self._send_command("TOGGLE_RTB", {"enabled": self.rtb_enabled})

    def _toggle_overkill(self):
        self.overkill_enabled = not self.overkill_enabled
        st = "ENABLED" if self.overkill_enabled else "DISABLED"
        self.btn_overkill.config(text=f"ANTI-OVERKILL: [{st}]")
        self._send_command("TOGGLE_OVERKILL", {"enabled": self.overkill_enabled})

    def _toggle_ai(self):
        self.ai_enabled = not self.ai_enabled
        st = "LAYA ON" if self.ai_enabled else "MANUAL"
        self.btn_ai.config(text=f"AI COMMANDER: [{st}]")
        self._send_command("TOGGLE_AI", {"enabled": self.ai_enabled})

    def _on_submit_cmd(self):
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return
        self.cmd_entry.delete(0, tk.END)
        self._log(f">> USER: {cmd}", "#38BDF8")
        self._send_command("OPERATOR_COMMAND", {"text": cmd})

    def _send_command(self, action: str, payload: dict):
        """Sends command message to Pygame simulation process."""
        try:
            self.command_queue.put_nowait({"action": action, "payload": payload})
        except Exception as e:
            self._log(f"[ERROR] Failed to send command: {e}", "#EF4444")

    def _log(self, text: str, color: str = None):
        self.log_txt.insert(tk.END, text + "\n")
        self.log_txt.see(tk.END)

    def _poll_telemetry(self):
        """Reads all pending telemetry packets from Pygame and updates charts."""
        latest_packet = None
        while True:
            try:
                packet = self.telemetry_queue.get_nowait()
                latest_packet = packet
            except Empty:
                break

        if latest_packet is not None:
            self._apply_telemetry(latest_packet)

        # Re-schedule polling in 100ms (10Hz)
        self.root.after(100, self._poll_telemetry)

    def _apply_telemetry(self, packet: dict):
        sim_time = packet.get("sim_time", 0.0)
        base_hp = packet.get("base_hp", 100.0)
        ammo_total = packet.get("ammo_total", 0)
        active_threats = packet.get("active_threats", 0)
        kills = packet.get("kills", 0)

        # Update history
        self.time_history.append(sim_time)
        self.base_hp_history.append(base_hp)
        self.ammo_history.append(ammo_total)
        self.threats_history.append(active_threats)
        self.kills_history.append(kills)

        if len(self.time_history) > self.max_history:
            self.time_history.pop(0)
            self.base_hp_history.pop(0)
            self.ammo_history.pop(0)
            self.threats_history.pop(0)
            self.kills_history.pop(0)

        # Update Matplotlib lines
        self.line_base.set_data(self.time_history, self.base_hp_history)
        self.line_ammo.set_data(self.time_history, self.ammo_history)
        self.line_threats.set_data(self.time_history, self.threats_history)
        self.line_kills.set_data(self.time_history, self.kills_history)

        t_min = self.time_history[0] if self.time_history else 0
        t_max = max(10.0, sim_time + 1.0)
        self.ax1.set_xlim(t_min, t_max)
        self.ax1.set_ylim(0, max(105.0, max(self.ammo_history) + 5 if self.ammo_history else 100.0))

        self.ax2.set_xlim(t_min, t_max)
        self.ax2.set_ylim(0, max(8, max(self.kills_history) + 2 if self.kills_history else 6))

        try:
            self.canvas.draw_idle()
        except Exception:
            pass

        # Update status bar
        leader_alive = packet.get("leader_alive", True)
        l_str = "ALIVE" if leader_alive else "KIA"
        self.status_lbl.config(
            text=f"TIME: {sim_time:05.1f}s | BASE: {base_hp:03.0f}% | LEADER: {l_str} | THREATS: {active_threats:02d} | KIA: {kills:02d}"
        )

        # Process log events
        events = packet.get("events", [])
        for ev in events:
            self._log(ev)


def run_dashboard_process(telemetry_queue: mp.Queue, command_queue: mp.Queue):
    """Entry point for child Tkinter dashboard process."""
    root = tk.Tk()
    app = TacticalDashboardApp(root, telemetry_queue, command_queue)
    root.mainloop()


class DashboardBridge:
    """
    Simulation-side bridge managing IPC queues and child process lifecycle.
    """
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.telemetry_queue = None
        self.command_queue = None
        self.process = None
        self.last_telemetry_time = 0.0
        self.telemetry_interval = 0.1  # 10 Hz telemetry export
        self.pending_events = []

        if self.enabled:
            self.start()

    def start(self):
        """Launches dashboard process."""
        try:
            # mp.set_start_method("spawn", force=False)
            self.telemetry_queue = mp.Queue(maxsize=100)
            self.command_queue = mp.Queue(maxsize=100)
            self.process = mp.Process(
                target=run_dashboard_process,
                args=(self.telemetry_queue, self.command_queue),
                daemon=True
            )
            self.process.start()
            print(f"[DashboardBridge] C2 Dashboard launched in PID {self.process.pid}.")
        except Exception as e:
            print(f"[DashboardBridge] Warning: could not launch Tkinter dashboard: {e}")
            self.enabled = False

    def emit_event(self, text: str):
        """Records an event string for transmission to the dashboard terminal."""
        if self.enabled:
            self.pending_events.append(text)

    def update(self, simulation, current_time: float):
        """
        Polls user commands from dashboard and pushes telemetry at 10Hz.
        Called once per Pygame frame inside simulation loop.
        """
        if not self.enabled:
            return

        # 1. Process Incoming Commands from Dashboard
        while True:
            try:
                cmd = self.command_queue.get_nowait()
                self._handle_command(cmd, simulation)
            except Empty:
                break
            except Exception:
                break

        # 2. Rate-limited Telemetry Push (10Hz)
        if current_time - self.last_telemetry_time >= self.telemetry_interval:
            self.last_telemetry_time = current_time
            self._push_telemetry(simulation, current_time)

    def _handle_command(self, cmd: dict, simulation):
        action = cmd.get("action")
        payload = cmd.get("payload", {})
        sm = getattr(simulation, "swarm_manager", None)
        if sm is None:
            return

        if action == "SET_FORMATION":
            form = payload.get("formation", "CIRCLE")
            sm.set_formation_strategy(form)
            self.emit_event(f"[C2 COMMAND] Formation switched to {form}")

        elif action == "SET_SLIDER":
            param = payload.get("param")
            val = payload.get("value")
            if param == "distance_chase":
                sm.distance_chase = val
                for d in sm.swarm:
                    d.distance_chase = val
            elif param == "formation_distance":
                sm.distance_formation = val
                if sm.leadingdrone:
                    sm.leadingdrone.distance_leader = val
                    list_pos = sm.leadingdrone.set_formation()
                    sm.goto_formation(list_pos)

        elif action == "SET_SPEED":
            spd = payload.get("speed", 1)
            simulation.accelerated_factor = spd

        elif action == "TOGGLE_RTB":
            en = payload.get("enabled", True)
            for d in sm.swarm:
                d.enable_rtb = en
            self.emit_event(f"[C2 COMMAND] RTB Logistics set to {en}")

        elif action == "TOGGLE_OVERKILL":
            en = payload.get("enabled", True)
            for d in sm.swarm:
                d.enable_anti_overkill = en
            self.emit_event(f"[C2 COMMAND] Anti-Overkill set to {en}")

        elif action == "TOGGLE_AI":
            en = payload.get("enabled", True)
            if hasattr(simulation, 'llm_commander') and simulation.llm_commander:
                simulation.llm_commander.enabled = en
            self.emit_event(f"[C2 COMMAND] AI Commander set to {en}")

        elif action == "SPAWN_THREAT":
            sm.add_kamikaze()
            self.emit_event(f"[C2 COMMAND] Hostile kamikaze spawned on perimeter.")

        elif action == "OPERATOR_COMMAND":
            text = payload.get("text", "").lower()
            if "wedge" in text:
                sm.set_formation_strategy("WEDGE")
                self.emit_event("[CO-PILOT] Understood: deploying WEDGE formation.")
            elif "wall" in text:
                sm.set_formation_strategy("WALL")
                self.emit_event("[CO-PILOT] Understood: deploying WALL defensive formation.")
            elif "circle" in text:
                sm.set_formation_strategy("CIRCLE")
                self.emit_event("[CO-PILOT] Understood: regrouping in CIRCLE umbrella.")
            elif "echelon" in text:
                sm.set_formation_strategy("ECHELON")
                self.emit_event("[CO-PILOT] Understood: deploying ECHELON formation.")
            elif "shield" in text or "base" in text:
                if hasattr(simulation, 'llm_commander') and simulation.llm_commander:
                    simulation.llm_commander.enabled = True
                self.emit_event("[CO-PILOT] Tactical priority updated: SHIELD BASE CORRIDOR.")
            else:
                self.emit_event(f"[CO-PILOT] Command acknowledged: '{text}'")

    def _push_telemetry(self, simulation, current_time: float):
        sm = getattr(simulation, "swarm_manager", None)
        if sm is None:
            return

        base = sm.protected_area
        base_hp = (base.life / 100.0) * 100.0 if base and hasattr(base, 'life') else 0.0

        total_ammo = 0
        for d in sm.swarm:
            if hasattr(d, 'vaporizer_gun'):
                total_ammo += d.vaporizer_gun.get_ammo_available()
            if hasattr(d, 'freezing_gun'):
                total_ammo += d.freezing_gun.get_ammo_available()

        active_threats = len([k for k in sm.kamikazes if not getattr(k, 'destroyed', False) and not getattr(k, 'explode', False)])
        leader_alive = sm.leadingdrone is not None and not getattr(sm.leadingdrone, 'destroyed', False)
        kills = sm.counter_kamikazes_destroyed

        events = list(self.pending_events)
        self.pending_events.clear()

        packet = {
            "sim_time": current_time,
            "base_hp": base_hp,
            "ammo_total": total_ammo,
            "active_threats": active_threats,
            "leader_alive": leader_alive,
            "kills": kills,
            "events": events
        }

        try:
            self.telemetry_queue.put_nowait(packet)
        except Exception:
            pass

    def stop(self):
        """Terminates dashboard child process."""
        if self.process and self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=1.0)
            print("[DashboardBridge] C2 Dashboard terminated.")


if __name__ == "__main__":
    # Test standalone dashboard
    t_q = mp.Queue()
    c_q = mp.Queue()
    p = mp.Process(target=run_dashboard_process, args=(t_q, c_q))
    p.start()

    print("Running standalone dashboard test for 5 seconds...")
    for step in range(50):
        time.sleep(0.1)
        sim_t = step * 0.1
        t_q.put({
            "sim_time": sim_t,
            "base_hp": max(0, 100 - step * 0.5),
            "ammo_total": max(0, 80 - step),
            "active_threats": 4 if step % 10 != 0 else 6,
            "leader_alive": True,
            "kills": step // 5,
            "events": [f"Datalink tick {step}"] if step % 20 == 0 else []
        })

    p.terminate()
    print("Standalone test completed successfully.")
