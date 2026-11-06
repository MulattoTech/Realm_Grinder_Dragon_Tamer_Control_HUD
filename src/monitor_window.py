"""
Realm Grinder - Dragon Tamer Quest Tracker & Control HUD (v4.5)
Constantly improving live desktop interface powered by 100% scraped G00F Not-a-Wiki data.
Includes:
- Complete Live ETA Engine: Real-time calculation for Next R, R46 Gate, and Total Dragon Tamer completion
- Autopilot Status Banner: Clarifies 24/7 hands-free background progression vs optional manual override buttons
- Visual Color & Status Legend: Explains green, cyan/blue, purple, amber, and dark slate button states
- Self-Explanatory Action Buttons: Plain-English subtitles and dynamic hover explanations for every button
- Zero-Red Clickable UX: Flame Amber for active farming, Dark Slate for locked prerequisites, Green for claimable
- Searchable Wiki Encyclopedia (252 Researches + 109 Trophies) & G00F Build Advisor
"""

import os
import sys
import json
import time
import math
import threading
from typing import Any, Dict, List, Optional
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import win32gui
import win32con

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_FILE = os.path.join(WORKSPACE_DIR, "state", "dragon_tamer_state.json")
STOP_FILE = os.path.join(WORKSPACE_DIR, "state", "STOP")
BACKUP_DIR = os.path.join(WORKSPACE_DIR, "backups")
LOG_FILE = os.path.join(WORKSPACE_DIR, "logs", "bot.log")

if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from src.config import load_config, save_config, update_setting
from src.telemetry import ProgressionTracker
from src.wiki_data import (
    DRAGON_UNLOCK_STAGES,
    BUILDS_DATABASE,
    get_recommended_build,
    get_reincarnation_gem_requirement,
    lookup_research,
    lookup_trophy,
    load_knowledge_base
)
from src.save_reader import extract_save_string_from_sol
from src.live_state import get_live_game_state
from src.telemetry_presenter import telemetry_banner,dragon_stage_views,mana_bar
from src.runtime_safety import input_allowed,require_interactive_session
from src.strategy_rules import PATH_CHOICES,selected_route
from src.source_knowledge import KnowledgeStore
from src.atomic_store import write_json
from src.gate_clearer import GateClearer
from src.ai_engine import SkynetOptimizationCore
from src.guardian import ProcessGuardian
from src.forecaster import MonteCarloArtifactForecaster, MilestoneForecaster
from src.state_machine import DragonBot


def pending_action_summary(pending):
    """Format the persisted evidence needed to investigate a blocked resume."""
    action=str(pending.get('action','unknown action'))
    action_id=str(pending.get('id','unknown id'))
    status=str(pending.get('status','unknown status'))
    error=str(pending.get('error','No failure detail was recorded.'))
    backup=str(pending.get('backup','No transaction backup was recorded.'))
    before=pending.get('before') or {}
    state=(f"Before action: R{before.get('reincarnation','?')}, faction {before.get('faction','?')}, "
           f"alignment {before.get('alignment','?')}, save {before.get('save_fingerprint','unknown')}.")
    return (f"Action: {action}\nID: {action_id}\nStatus: {status}\n{state}\n"
            f"Recorded result: {error}\nBackup: {backup}\n\n"
            "The action remains unresolved. No retry was sent; inspect the current game and backup before reconciling.")

NOTATIONS = [
    (1e99, "Dtg (1e99)"),
    (1e96, "Utg (1e96)"),
    (1e93, "Ttg (1e93)"),
    (1e90, "Nog (1e90)"),
    (1e87, "Ocg (1e87)"),
    (1e84, "Spg (1e84)"),
    (1e81, "Sxg (1e81)"),
    (1e78, "Qig (1e78)"),
    (1e75, "Qag (1e75)"),
    (1e72, "Tvg (1e72)"),
    (1e69, "Dvg (1e69)"),
    (1e66, "Uvg (1e66)"),
    (1e63, "Vg (1e63)"),
    (1e60, "Nod (1e60)"),
    (1e57, "Ocd (1e57)"),
    (1e54, "Spd (1e54)"),
    (1e51, "Sxd (1e51)"),
    (1e48, "Qid (1e48)"),
    (1e45, "Qad (1e45)"),
    (1e42, "Td (1e42)"),
    (1e39, "Dd (1e39)"),
    (1e36, "Ud (1e36)"),
    (1e33, "Dc (1e33)"),
    (1e30, "No (1e30)"),
    (1e27, "Oc (1e27)"),
    (1e24, "Sp (1e24)"),
    (1e21, "Sx (1e21)"),
    (1e18, "Qi (1e18)"),
    (1e15, "Qa (1e15)"),
    (1e12, "T (1e12)"),
    (1e9, "B (1e9)"),
    (1e6, "M (1e6)"),
    (1e3, "K (1e3)")
]

def format_rg_num(val: float) -> str:
    if val is None or math.isnan(val):
        return "0"
    if val < 1000:
        return f"{val:.1f}"
    if val >= 1e102:
        return f"{val:.3e}"
    for threshold, suffix in NOTATIONS:
        if val >= threshold:
            return f"{val / threshold:.3f} {suffix}"
    return f"{val:.3e}"


class ModernDragonTrackerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Dragon Tamer Quest Tracker & Control HUD")
        self.root.geometry("640x950+1280+10")
        self.root.minsize(580, 800)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#121318")

        ico_file = os.path.join(os.path.dirname(__file__), "..", "assets", "dragon_tamer.ico")
        if os.path.exists(ico_file):
            try:
                self.root.iconbitmap(ico_file)
            except Exception:
                pass

        self.telemetry = ProgressionTracker()
        self.config = load_config()
        self.clearer = GateClearer()
        self.ai = SkynetOptimizationCore()
        self.guardian = ProcessGuardian()

        # Theme Colors
        self.c_bg = "#121318"
        self.c_panel = "#1a1b24"
        self.c_card = "#21232e"
        self.c_border = "#2f3342"
        self.c_gold = "#f5a623"
        self.c_cyan = "#00e5c0"
        self.c_blue = "#1b6ca8"
        self.c_green = "#2ecc71"
        self.c_purple = "#8e44ad"
        self.c_amber = "#e67e22"
        self.c_dark = "#1c1f2b"
        self.c_red = "#ff4757"
        self.c_text = "#e6e8ee"
        self.c_muted = "#8e94a6"
        self.c_accent = "#6c5ce7"

        self.setup_styles()
        self.setup_ui()
        self.last_log_pos = 0
        self.is_clearing_gate = False

        # Autonomous Background Worker Daemon Thread
        self.bot = DragonBot()
        self.worker_thread = threading.Thread(target=self.bot.run_loop, daemon=True)
        self.worker_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.update_loop)
        self.root.after(250, self.update_mana_bar)


    def on_close(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=self.c_bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.c_panel, foreground=self.c_muted, font=("Segoe UI", 8, "bold"), padding=[8, 5])
        style.map("TNotebook.Tab", background=[("selected", self.c_card)], foreground=[("selected", self.c_cyan)])

        style.configure("Green.Horizontal.TProgressbar", foreground=self.c_green, background=self.c_green, troughcolor="#1a1b24", borderwidth=0)
        style.configure("Cyan.Horizontal.TProgressbar", foreground=self.c_cyan, background=self.c_cyan, troughcolor="#1a1b24", borderwidth=0)
        style.configure("Gold.Horizontal.TProgressbar", foreground=self.c_gold, background=self.c_gold, troughcolor="#1a1b24", borderwidth=0)

    def bind_hover(self, widget, msg: str):
        """Binds mouse hover to display contextual explanation in the bottom feedback bar."""
        widget.bind("<Enter>", lambda e: self.set_feedback(msg, self.c_cyan))
        widget.bind("<Leave>", lambda e: self.set_feedback("Review the selected path, next prerequisite, telemetry and pause state."))

    def setup_ui(self):
        # 1. Header Banner
        header = tk.Frame(self.root, bg=self.c_panel, bd=0, highlightbackground=self.c_border, highlightthickness=1)
        header.pack(fill="x", padx=8, pady=(6, 3))

        top_row = tk.Frame(header, bg=self.c_panel)
        top_row.pack(fill="x", padx=8, pady=(4, 2))

        title_lbl = tk.Label(top_row, text="DRAGON TAMER QUEST TRACKER", font=("Segoe UI", 10, "bold"), fg=self.c_gold, bg=self.c_panel)
        title_lbl.pack(side="left")

        self.ultron_badge = tk.Label(top_row, text="⚡ ULTRONBURST v5.2 ACTIVE", font=("Segoe UI", 8, "bold"), fg=self.c_gold, bg="#1e180a", padx=6, pady=2)
        self.ultron_badge.pack(side="right")

        self.status_row = tk.Frame(header, bg=self.c_panel)
        self.status_row.pack(fill="x", padx=8, pady=(2, 3))

        self.worker_badge = tk.Label(self.status_row, text="🤖 24/7 Autopilot", font=("Segoe UI", 8, "bold"), fg=self.c_green, bg="#0d2218", padx=6, pady=2)
        self.worker_badge.pack(side="left")

        self.window_state_badge = tk.Label(self.status_row, text="🗕 Minimized", font=("Segoe UI", 8, "bold"), fg=self.c_cyan, bg="#0c202a", padx=6, pady=2)
        self.window_state_badge.pack(side="left", padx=6)

        # ETA pill cleanly on right side
        eta_pill = tk.Frame(self.status_row, bg="#141c2b", highlightbackground=self.c_cyan, highlightthickness=1)
        eta_pill.pack(side="right")

        self.overall_eta_lbl = tk.Label(eta_pill, text="⏳ ETA: Calculating...", font=("Segoe UI", 8, "bold"), fg=self.c_cyan, bg="#141c2b", padx=6, pady=1)
        self.overall_eta_lbl.pack(side="left")

        self.overall_target_lbl = tk.Label(eta_pill, text="", font=("Segoe UI", 7), fg=self.c_muted, bg="#141c2b", padx=2, pady=1)
        self.overall_target_lbl.pack(side="left", padx=(0, 6))

        # Hands-free notification banner
        handsfree_bar = tk.Frame(header, bg="#131722")
        handsfree_bar.pack(fill="x", padx=4, pady=(1, 3))
        self.hf_lbl = tk.Label(handsfree_bar, wraplength=590, anchor="w", text="💡 24/7 Background Autopilot active.", font=("Segoe UI", 7), fg=self.c_muted, bg="#131722", justify="left")
        self.hf_lbl.pack(fill="x", padx=6, pady=2)

        # Live volatile mana bar row
        mana_row = tk.Frame(header, bg="#0e1520", highlightbackground="#00555a", highlightthickness=1)
        mana_row.pack(fill="x", padx=4, pady=(0, 3))

        self.mem_badge = tk.Label(mana_row, text="[MEM]", font=("Consolas", 7, "bold"),
                                  fg="#00e5c0", bg="#0e1520", padx=4, pady=1)
        self.mem_badge.pack(side="left")

        mana_inner = tk.Frame(mana_row, bg="#0e1520")
        mana_inner.pack(side="left", fill="x", expand=True, padx=4)

        self.mana_label = tk.Label(mana_inner, text="Mana: — / — | Regen: —/s",
                                   font=("Segoe UI", 7, "bold"), fg=self.c_cyan, bg="#0e1520", anchor="w")
        self.mana_label.pack(fill="x")

        self.mana_bar_prog = ttk.Progressbar(mana_inner, style="Cyan.Horizontal.TProgressbar",
                                              length=100, mode="determinate")
        self.mana_bar_prog.pack(fill="x", pady=(1, 0))

        self.mem_source_lbl = tk.Label(mana_row, text="SAVE", font=("Segoe UI", 7),
                                       fg=self.c_muted, bg="#0e1520", padx=4)
        self.mem_source_lbl.pack(side="right")


        # 2. Segmented Navigation Tabs
        tab_bar = tk.Frame(self.root, bg=self.c_bg)
        tab_bar.pack(fill="x", padx=8, pady=(2, 4))

        self.tab_buttons = {}
        self.active_tab = "quest"

        tab_defs = [
            ("quest", "📜 Quest & ETAs"),
            ("skynet", "🧠 Skynet AI Core"),
            ("advisor", "📖 Build Advisor"),
            ("wiki", "📚 Wiki Lookup"),
            ("controls", "⚙ Automation"),
            ("logs", "📊 Logs & History")
        ]

        for tid, tname in tab_defs:
            btn = tk.Button(
                tab_bar, text=tname, font=("Segoe UI", 8, "bold"),
                bg=self.c_card if tid == "quest" else self.c_panel,
                fg=self.c_cyan if tid == "quest" else self.c_muted,
                activebackground=self.c_card, activeforeground=self.c_cyan,
                relief="flat", bd=0, padx=4, pady=4, cursor="hand2",
                command=lambda t=tid: self.switch_tab(t)
            )
            btn.pack(side="left", padx=(0, 2), expand=True, fill="x")
            self.tab_buttons[tid] = btn

        # Container for tabs
        self.container = tk.Frame(self.root, bg=self.c_bg)
        self.container.pack(fill="both", expand=True, padx=8, pady=2)

        self.tab_quest = tk.Frame(self.container, bg=self.c_bg)
        self.tab_skynet = tk.Frame(self.container, bg=self.c_bg)
        self.tab_advisor = tk.Frame(self.container, bg=self.c_bg)
        self.tab_wiki = tk.Frame(self.container, bg=self.c_bg)
        self.tab_controls = tk.Frame(self.container, bg=self.c_bg)
        self.tab_logs = tk.Frame(self.container, bg=self.c_bg)

        self.build_tab_quest()
        self.build_tab_skynet()
        self.build_tab_advisor()
        self.build_tab_wiki()
        self.build_tab_controls()
        self.build_tab_logs()

        self.tab_quest.pack(fill="both", expand=True)

        # 3. Action Feedback Toast Bar
        self.feedback_bar = tk.Frame(self.root, bg="#181a24", highlightbackground=self.c_border, highlightthickness=1)
        self.feedback_bar.pack(fill="x", padx=8, pady=(2, 2))

        self.feedback_lbl = tk.Label(
            self.feedback_bar, text="Review the selected path, next prerequisite, telemetry and pause state.",
            font=("Segoe UI", 8), fg=self.c_muted, bg="#181a24", anchor="w"
        )
        self.feedback_lbl.pack(fill="x", padx=8, pady=3)

        # 4. Persistent Action Footer
        footer = tk.Frame(self.root, bg=self.c_panel, highlightbackground=self.c_border, highlightthickness=1)
        footer.pack(fill="x", padx=8, pady=(2, 6))

        self.backup_btn = tk.Button(
            footer, text="⚡ Safe Backup", font=("Segoe UI", 8, "bold"),
            bg="#243342", fg=self.c_text, activebackground="#34495e", activeforeground="white",
            relief="flat", padx=8, pady=3, cursor="hand2", command=self.action_backup
        )
        self.backup_btn.pack(side="left", padx=6, pady=4)
        self.bind_hover(self.backup_btn, "Safe Backup: Exports and verifies a complete copy of the live save to backups/ directory.")

        self.snap_btn = tk.Button(
            footer, text="📸 State Snapshot", font=("Segoe UI", 8, "bold"),
            bg="#213c47", fg=self.c_cyan, activebackground="#2c5160", activeforeground="white",
            relief="flat", padx=8, pady=3, cursor="hand2", command=self.action_snapshot_state
        )
        self.snap_btn.pack(side="left", padx=4, pady=4)
        self.bind_hover(self.snap_btn, "State Snapshot: Takes a full visual screenshot (even if minimized) and captures complete game telemetry for future calculations.")

        self.pause_btn = tk.Button(
            footer, text="⏸ Pause Bot", font=("Segoe UI", 8, "bold"),
            bg="#8b2626", fg="white", activebackground="#a93226", activeforeground="white",
            relief="flat", padx=8, pady=3, cursor="hand2", command=self.action_toggle_pause
        )
        self.pause_btn.pack(side="left", padx=4, pady=4)
        self.bind_hover(self.pause_btn, "Pause/Resume Bot: Suspends or resumes the 24/7 autonomous background bot loop.")

        self.refresh_btn = tk.Button(
            footer, text="🔄 Refresh Save", font=("Segoe UI", 8),
            bg="#2c303d", fg=self.c_text, activebackground="#3d4355", activeforeground="white",
            relief="flat", padx=6, pady=3, cursor="hand2", command=self.action_force_refresh
        )
        self.refresh_btn.pack(side="right", padx=6, pady=4)
        self.bind_hover(self.refresh_btn, "Refresh Save: Immediately re-reads and re-decodes the live game save file from disk.")

    def switch_tab(self, tid: str):
        self.active_tab = tid
        for k, btn in self.tab_buttons.items():
            if k == tid:
                btn.configure(bg=self.c_card, fg=self.c_cyan)
            else:
                btn.configure(bg=self.c_panel, fg=self.c_muted)

        for tab_frame in [self.tab_quest, self.tab_skynet, self.tab_advisor, self.tab_wiki, self.tab_controls, self.tab_logs]:
            tab_frame.pack_forget()

        if tid == "quest":
            self.tab_quest.pack(fill="both", expand=True)
        elif tid == "skynet":
            self.tab_skynet.pack(fill="both", expand=True)
        elif tid == "advisor":
            self.tab_advisor.pack(fill="both", expand=True)
        elif tid == "wiki":
            self.tab_wiki.pack(fill="both", expand=True)
        elif tid == "controls":
            self.tab_controls.pack(fill="both", expand=True)
        elif tid == "logs":
            self.tab_logs.pack(fill="both", expand=True)

    def set_feedback(self,msg,color=None):
        def apply():
            if self.root.winfo_exists():self.feedback_lbl.configure(text=msg,fg=color or self.c_muted)
        if threading.current_thread() is threading.main_thread():apply()
        else:self.root.after(0,apply)

    def build_tab_quest(self):
        # 0. Skynet AI Live Decision Banner
        ai_banner = tk.Frame(self.tab_quest, bg="#101826", highlightbackground=self.c_accent, highlightthickness=1)
        ai_banner.pack(fill="x", padx=4, pady=(2, 2))
        self.skynet_banner_lbl = tk.Label(
            ai_banner, text="🧠 SKYNET AI CORE: Initializing omniscient calculus engine...",
            font=("Segoe UI", 7, "bold"), fg=self.c_cyan, bg="#101826", anchor="w", padx=6, pady=2
        )
        self.skynet_banner_lbl.pack(fill="x")

        # PRIMARY 1-CLICK GOAL BUTTON — Automate Straight to Goal
        goal_btn_frame = tk.Frame(self.tab_quest, bg="#0d1520",
                                  highlightbackground=self.c_gold, highlightthickness=1)
        goal_btn_frame.pack(fill="x", padx=4, pady=(2, 2))

        self.automate_btn = tk.Button(
            goal_btn_frame,
            text="⚡ Automate Straight to Goal",
            font=("Segoe UI", 11, "bold"),
            bg="#1c2a10", fg=self.c_gold,
            activebackground="#2e4418", activeforeground="#ffe680",
            relief="flat", padx=12, pady=6, cursor="hand2",
            command=self.action_automate_straight_to_goal
        )
        self.automate_btn.pack(side="left", padx=8, pady=6)

        self.automate_status_lbl = tk.Label(
            goal_btn_frame,
            text="Configure path & goal above, then click to start full autonomous progression.",
            font=("Segoe UI", 8), fg=self.c_muted, bg="#0d1520",
            wraplength=380, justify="left", anchor="w"
        )
        self.automate_status_lbl.pack(side="left", fill="x", expand=True, padx=6)

        self.bind_hover(self.automate_btn,
            "⚡ Automate Straight to Goal: Sets game to non-intrusive background mode, unpauses the worker, "
            "and runs full autonomous progression — build setup, spell casting, abdications, reincarnations — "
            "until the selected goal is reached. One worker owner; no focus theft.")

        # 1. Master Auto-Clear Header Banner
        banner = tk.Frame(self.tab_quest, bg="#1a2234", highlightbackground=self.c_cyan, highlightthickness=1)
        banner.pack(fill="x", padx=4, pady=(2, 2))


        b_info = tk.Frame(banner, bg="#1a2234")
        b_info.pack(side="left", fill="both", expand=True, padx=8, pady=4)

        self.active_gate_lbl = tk.Label(b_info, text="⚡ Active Bottleneck: Gate 0 (Reincarnation R24 -> R25)", font=("Segoe UI", 9, "bold"), fg=self.c_gold, bg="#1a2234", anchor="w")
        self.active_gate_lbl.pack(fill="x")

        self.active_gate_sublbl = tk.Label(b_info, text="Target: 1.000 Dtg Gems | Running on 24/7 Autopilot. Manual click is optional.", font=("Segoe UI", 7), fg=self.c_muted, bg="#1a2234", anchor="w")
        self.active_gate_sublbl.pack(fill="x")

        self.master_clear_btn = tk.Button(
            banner, text="⚡ FORCE FAST-TRACK\nACTIVE GATE NOW", font=("Segoe UI", 8, "bold"),
            bg="#00b894", fg="#0d1117", activebackground="#00e5c0", activeforeground="black",
            relief="flat", padx=8, pady=2, cursor="hand2", command=self.action_fast_track
        )
        self.master_clear_btn.pack(side="right", padx=6, pady=4)
        self.bind_hover(self.master_clear_btn, "Runs the selected path through the single action owner. Unknown or unmet requirements remain visible blockers.")

        # The selected path is an executable preference, not just advisory text.
        path_row=tk.Frame(self.tab_quest,bg=self.c_panel)
        path_row.pack(fill='x',padx=4,pady=3)
        tk.Label(path_row,text='Path:',bg=self.c_panel,fg=self.c_gold,font=('Segoe UI',8)).pack(side='left',padx=4)
        self.path_var=tk.StringVar(value=load_config().get('selected_path','Automatic'))
        self.path_combo=ttk.Combobox(path_row,textvariable=self.path_var,values=PATH_CHOICES,state='readonly',width=19)
        self.path_combo.pack(side='left',padx=2)
        self.path_combo.bind('<<ComboboxSelected>>',lambda event:self.save_selected_path())
        self.goal_var=tk.StringVar(value=load_config().get('selected_goal','Dragon Tamer'))
        self.goal_combo=ttk.Combobox(path_row,textvariable=self.goal_var,
            values=('Dragon Tamer','Next reincarnation','Build only','Named goal'),state='readonly',width=17)
        self.goal_combo.pack(side='left',padx=3)
        self.goal_combo.bind('<<ComboboxSelected>>',lambda event:self.save_selected_path())
        tk.Button(path_row,text='Start path',command=self.start_selected_path,bg=self.c_cyan,fg=self.c_bg,
                  font=('Segoe UI',8,'bold'),relief='flat').pack(side='right',padx=4)

        target_row=tk.Frame(self.tab_quest,bg=self.c_panel)
        target_row.pack(fill='x',padx=4,pady=(0,3))
        tk.Label(target_row,text='Named goal:',bg=self.c_panel,fg=self.c_muted,font=('Segoe UI',8)).pack(side='left',padx=4)
        self.named_goal_var=tk.StringVar(value=load_config().get('named_goal','Dragon Tamer'))
        from src.knowledge_service import KnowledgeService
        known_targets=tuple(KnowledgeService().book.rules)
        self.named_goal_combo=ttk.Combobox(target_row,textvariable=self.named_goal_var,values=known_targets,width=30)
        self.named_goal_combo.pack(side='left',padx=3)
        self.named_goal_combo.bind('<<ComboboxSelected>>',lambda event:self.save_selected_path())
        tk.Button(target_row,text='Inspect requirements',command=self.inspect_named_goal,bg=self.c_panel,fg=self.c_cyan,
                  relief='flat',font=('Segoe UI',8)).pack(side='right',padx=4)

        # 3. Gate 0: Reincarnation Progression to R46
        r_card = tk.LabelFrame(
            self.tab_quest, text=" Gate 0: Reincarnation Progression to R46 (Dragon Prerequisite) ",
            font=("Segoe UI", 8, "bold"), fg=self.c_cyan, bg=self.c_card,
            bd=1, relief="solid", highlightbackground=self.c_border
        )
        r_card.pack(fill="x", padx=4, pady=(2, 2))

        r_header = tk.Frame(r_card, bg=self.c_card)
        r_header.pack(fill="x", padx=8, pady=(2, 1))

        self.r_val_lbl = tk.Label(r_header, text="Reincarnation: R24 / R46 (52.2%)", font=("Segoe UI", 9, "bold"), fg=self.c_text, bg=self.c_card)
        self.r_val_lbl.pack(side="left")

        self.r46_eta_badge = tk.Label(r_header, text="R46 ETA: Calculating...", font=("Segoe UI", 8, "bold"), fg=self.c_gold, bg=self.c_card)
        self.r46_eta_badge.pack(side="right")

        self.r_prog = ttk.Progressbar(r_card, style="Cyan.Horizontal.TProgressbar", length=100, mode="determinate")
        self.r_prog.pack(fill="x", padx=8, pady=(2, 3))

        stats_grid = tk.Frame(r_card, bg=self.c_card)
        stats_grid.pack(fill="x", padx=8, pady=(0, 2))

        self.gems_lbl = tk.Label(stats_grid, text="Gems: 16.550 Ocd (1e58)", font=("Segoe UI", 8), fg=self.c_text, bg=self.c_card)
        self.gems_lbl.grid(row=0, column=0, sticky="w", padx=4, pady=1)

        self.pot_gems_lbl = tk.Label(stats_grid, text="Pot Gems: 0.000", font=("Segoe UI", 8), fg=self.c_cyan, bg=self.c_card)
        self.pot_gems_lbl.grid(row=0, column=1, sticky="w", padx=16, pady=1)

        self.coins_lbl = tk.Label(stats_grid, text="Coins: 0.000", font=("Segoe UI", 8), fg=self.c_gold, bg=self.c_card)
        self.coins_lbl.grid(row=1, column=0, sticky="w", padx=4, pady=1)

        self.goal_lbl = tk.Label(stats_grid, text="R25 Goal: 1.000 Dtg (1e99)", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_card)
        self.goal_lbl.grid(row=1, column=1, sticky="w", padx=16, pady=1)

        # Gate 0 Action Buttons Row
        r_btn_row = tk.Frame(r_card, bg=self.c_card)
        r_btn_row.pack(fill="x", padx=8, pady=(2, 4))

        self.btn_clear_r = tk.Button(
            r_btn_row, text="🟣 Auto-Climb R (Force Cycle)", font=("Segoe UI", 7, "bold"),
            bg=self.c_purple, fg="white", activebackground="#9b59b6", activeforeground="white",
            relief="flat", padx=6, pady=2, cursor="hand2", command=self.action_clear_reincarnation
        )
        self.btn_clear_r.pack(side="left", padx=(0, 4))
        self.bind_hover(self.btn_clear_r, "Auto-Climb R: (Manual override) Immediately executes production push, build deployment, or reincarnation for current R.")

        self.btn_abdicate = tk.Button(
            r_btn_row, text="💫 Abdicate Now (Claim Gems)", font=("Segoe UI", 7, "bold"),
            bg="#16a085", fg="white", activebackground="#1abc9c", activeforeground="white",
            relief="flat", padx=6, pady=2, cursor="hand2", command=self.action_manual_abdicate
        )
        self.btn_abdicate.pack(side="left", padx=4)
        self.bind_hover(self.btn_abdicate, "Abdicate Now: (Manual override) Safely abdicates with automatic backup to convert coins into permanent gems.")

        self.btn_reincarnate = tk.Button(
            r_btn_row, text="🔄 Reincarnate (Locked)", font=("Segoe UI", 7, "bold"),
            bg=self.c_dark, fg=self.c_muted, state="disabled", relief="flat", padx=6, pady=2,
            command=self.action_manual_reincarnate
        )
        self.btn_reincarnate.pack(side="left", padx=4)
        self.bind_hover(self.btn_reincarnate, "Reincarnate: Unlocks in Green when current gems reach target. Reincarnates to next R level.")

        # 4. Card 2: Dragon Stages (Gates 1 to 5)
        dragon_card = tk.LabelFrame(
            self.tab_quest, text=" Dragon Unlock Stages (Automated Progression & Overrides) ",
            font=("Segoe UI", 8, "bold"), fg=self.c_gold, bg=self.c_card,
            bd=1, relief="solid", highlightbackground=self.c_border
        )
        dragon_card.pack(fill="both", expand=True, padx=4, pady=2)

        self.stage_cards = {}
        for s_id, s_info in DRAGON_UNLOCK_STAGES.items():
            f = tk.Frame(dragon_card, bg="#1a1b24", highlightbackground=self.c_border, highlightthickness=1)
            f.pack(fill="x", padx=6, pady=2)

            # Row 1: Title and Status Badge
            top = tk.Frame(f, bg="#1a1b24")
            top.pack(fill="x", padx=6, pady=(2, 1))

            name_lbl = tk.Label(top, text=f"Stage {s_id}: {s_info['name']}", font=("Segoe UI", 8, "bold"), fg=self.c_gold, bg="#1a1b24")
            name_lbl.pack(side="left")

            status_lbl = tk.Label(top, text="LOCKED (Requires R46+)", font=("Segoe UI", 7, "bold"), fg=self.c_red, bg="#1a1b24")
            status_lbl.pack(side="right")

            # Row 2: Live Progress Details
            mid = tk.Frame(f, bg="#1a1b24")
            mid.pack(fill="x", padx=6, pady=(1, 1))

            prog_lbl = tk.Label(mid, text="Progress: Calculating...", font=("Segoe UI", 7), fg=self.c_cyan, bg="#1a1b24")
            prog_lbl.pack(side="left")

            prog_bar = ttk.Progressbar(f, style="Gold.Horizontal.TProgressbar", length=100, mode="determinate")
            prog_bar.pack(fill="x", padx=6, pady=(1, 2))

            # Row 3: Description and Action "Clear Gate" Button
            bot = tk.Frame(f, bg="#1a1b24")
            bot.pack(fill="x", padx=6, pady=(1, 3))

            req_txt = s_info.get("description", "")
            req_lbl = tk.Label(bot, text=req_txt, font=("Segoe UI", 7), fg=self.c_muted, bg="#1a1b24", anchor="w")
            req_lbl.pack(side="left", fill="x", expand=True)

            clear_btn = tk.Button(
                bot, text=f"⚡ Action {s_id}", font=("Segoe UI", 7, "bold"),
                bg=self.c_dark, fg=self.c_muted, state="disabled", relief="flat", padx=6, pady=1,
                command=lambda sid=s_id: self.action_clear_gate(sid)
            )
            clear_btn.pack(side="right", padx=(4, 0))

            self.stage_cards[s_id] = {
                "frame": f,
                "status_lbl": status_lbl,
                "prog_lbl": prog_lbl,
                "prog_bar": prog_bar,
                "req_lbl": req_lbl,
                "clear_btn": clear_btn
            }

    def build_tab_skynet(self):
        # 1. Main Neural Brain Directive Card
        brain_card = tk.LabelFrame(
            self.tab_skynet, text=" Skynet Omniscient Neural Decision Core ",
            font=("Segoe UI", 8, "bold"), fg=self.c_gold, bg=self.c_card,
            bd=1, relief="solid", highlightbackground=self.c_border
        )
        brain_card.pack(fill="x", padx=4, pady=(2, 3))

        b_top = tk.Frame(brain_card, bg=self.c_card)
        b_top.pack(fill="x", padx=8, pady=(4, 2))

        self.skynet_directive_badge = tk.Label(
            b_top, text="⚡ DIRECTIVE: COMPOUND_PRODUCTION",
            font=("Consolas", 9, "bold"), fg=self.c_cyan, bg="#141724", padx=6, pady=2
        )
        self.skynet_directive_badge.pack(side="left")

        self.ultron_burst_badge = tk.Label(
            b_top, text="⚡ ULTRONBURST: ENGAGED",
            font=("Consolas", 8, "bold"), fg=self.c_gold, bg="#1e180a", padx=6, pady=2
        )
        self.ultron_burst_badge.pack(side="left", padx=8)

        self.skynet_priority_badge = tk.Label(
            b_top, text="Priority: 10 / 100", font=("Segoe UI", 8, "bold"),
            fg=self.c_gold, bg=self.c_card
        )
        self.skynet_priority_badge.pack(side="right")

        lbl_stream = tk.Label(brain_card, text="Omniscient AI Thought Stream & Mathematical Rationale:", font=("Segoe UI", 7, "bold"), fg=self.c_muted, bg=self.c_card)
        lbl_stream.pack(anchor="w", padx=8, pady=(2, 1))

        self.skynet_thought_text = tk.Text(
            brain_card, height=3, font=("Segoe UI", 8), bg="#14161f", fg=self.c_text,
            bd=1, relief="solid", highlightbackground=self.c_border, wrap="word"
        )
        self.skynet_thought_text.pack(fill="x", padx=8, pady=(0, 4))

        # 2. Calculus Derivative Telemetry Card
        calc_card = tk.LabelFrame(
            self.tab_skynet, text=" Real-Time Calculus Derivatives & Growth Saturation ",
            font=("Segoe UI", 8, "bold"), fg=self.c_cyan, bg=self.c_card,
            bd=1, relief="solid", highlightbackground=self.c_border
        )
        calc_card.pack(fill="x", padx=4, pady=2)

        sat_row = tk.Frame(calc_card, bg=self.c_card)
        sat_row.pack(fill="x", padx=8, pady=(2, 1))

        tk.Label(sat_row, text="Growth Saturation (Inflection Point):", font=("Segoe UI", 8), fg=self.c_text, bg=self.c_card).pack(side="left")
        self.skynet_sat_pct_lbl = tk.Label(sat_row, text="0.0% (Accelerating)", font=("Segoe UI", 8, "bold"), fg=self.c_green, bg=self.c_card)
        self.skynet_sat_pct_lbl.pack(side="right")

        self.skynet_sat_bar = ttk.Progressbar(calc_card, style="Gold.Horizontal.TProgressbar", length=100, mode="determinate")
        self.skynet_sat_bar.pack(fill="x", padx=8, pady=(0, 4))

        metrics_grid = tk.Frame(calc_card, bg=self.c_card)
        metrics_grid.pack(fill="x", padx=8, pady=(0, 4))

        self.skynet_vel_lbl = tk.Label(metrics_grid, text="Gem Velocity (dG/dt): 0.00 /s", font=("Segoe UI", 8), fg=self.c_cyan, bg=self.c_card)
        self.skynet_vel_lbl.grid(row=0, column=0, sticky="w", padx=4, pady=1)

        self.skynet_acc_lbl = tk.Label(metrics_grid, text="Acceleration (d²G/dt²): 0.00 /s²", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_card)
        self.skynet_acc_lbl.grid(row=0, column=1, sticky="w", padx=16, pady=1)

        self.skynet_elapsed_lbl = tk.Label(metrics_grid, text="Current Run Duration: 0m 00s", font=("Segoe UI", 8), fg=self.c_text, bg=self.c_card)
        self.skynet_elapsed_lbl.grid(row=1, column=0, sticky="w", padx=4, pady=1)

        self.skynet_inflect_lbl = tk.Label(metrics_grid, text="Projected Inflection: Dynamic", font=("Segoe UI", 8), fg=self.c_gold, bg=self.c_card)
        self.skynet_inflect_lbl.grid(row=1, column=1, sticky="w", padx=16, pady=1)

        # 3. Monte Carlo Artifact Simulation Card (Spiky Rough Egg Artifact 211)
        mc_card = tk.LabelFrame(
            self.tab_skynet, text=" Monte Carlo Probability Engine (Spiky Rough Egg Artifact 211) ",
            font=("Segoe UI", 8, "bold"), fg=self.c_gold, bg=self.c_card,
            bd=1, relief="solid", highlightbackground=self.c_border
        )
        mc_card.pack(fill="x", padx=4, pady=2)

        mc_grid = tk.Frame(mc_card, bg=self.c_card)
        mc_grid.pack(fill="x", padx=8, pady=3)

        self.mc_chance_lbl = tk.Label(mc_grid, text="Drop Chance per Dig: 0.000% (Unlocks at R46, 1500+ digs)", font=("Segoe UI", 8, "bold"), fg=self.c_cyan, bg=self.c_card)
        self.mc_chance_lbl.grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=1)

        self.mc_p50_lbl = tk.Label(mc_grid, text="P50 (Median Drop): ~476 digs past 1500", font=("Segoe UI", 8), fg=self.c_text, bg=self.c_card)
        self.mc_p50_lbl.grid(row=1, column=0, sticky="w", padx=4, pady=1)

        self.mc_p90_lbl = tk.Label(mc_grid, text="P90 (90% Confidence): ~1,060 digs", font=("Segoe UI", 8), fg=self.c_text, bg=self.c_card)
        self.mc_p90_lbl.grid(row=1, column=1, sticky="w", padx=16, pady=1)

        self.mc_p99_lbl = tk.Label(mc_grid, text="P99 (conditional probability): ~1,682 digs", font=("Segoe UI", 8), fg=self.c_gold, bg=self.c_card)
        self.mc_p99_lbl.grid(row=2, column=0, sticky="w", padx=4, pady=1)

        self.mc_cost_lbl = tk.Label(mc_grid, text="Target Reincarnation: R46 required", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_card)
        self.mc_cost_lbl.grid(row=2, column=1, sticky="w", padx=16, pady=1)

        # 4. Self-Healing Process Guardian Matrix Card
        guard_card = tk.LabelFrame(
            self.tab_skynet, text=" Process Guardian & Self-Healing Matrix (Zero-Downtime Guarantee) ",
            font=("Segoe UI", 8, "bold"), fg=self.c_green, bg=self.c_card,
            bd=1, relief="solid", highlightbackground=self.c_border
        )
        guard_card.pack(fill="both", expand=True, padx=4, pady=2)

        g_grid = tk.Frame(guard_card, bg=self.c_card)
        g_grid.pack(fill="x", padx=8, pady=3)

        self.g_status_lbl = tk.Label(g_grid, text="🛡️ Steam Client: ACTIVE & HEALTHY", font=("Segoe UI", 8, "bold"), fg=self.c_green, bg=self.c_card)
        self.g_status_lbl.grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=1)

        self.g_win_lbl = tk.Label(g_grid, text="🗕 Window State: 100% Minimized (Background Safe)", font=("Segoe UI", 8), fg=self.c_cyan, bg=self.c_card)
        self.g_win_lbl.grid(row=1, column=0, sticky="w", padx=4, pady=1)

        self.g_hash_lbl = tk.Label(g_grid, text="Save SHA256: Verified & Validated", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_card)
        self.g_hash_lbl.grid(row=1, column=1, sticky="w", padx=16, pady=1)

        self.g_restarts_lbl = tk.Label(g_grid, text="Auto-Heal Crashes: 0 (Flawless Stability)", font=("Segoe UI", 8), fg=self.c_text, bg=self.c_card)
        self.g_restarts_lbl.grid(row=2, column=0, sticky="w", padx=4, pady=1)

        self.g_backup_lbl = tk.Label(g_grid, text="Rolling Backups: Active & Pruned", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_card)
        self.g_backup_lbl.grid(row=2, column=1, sticky="w", padx=16, pady=1)

    def build_tab_advisor(self):
        card = tk.LabelFrame(
            self.tab_advisor, text=" G00F Not-a-Wiki Optimal Build Advisor ",
            font=("Segoe UI", 8, "bold"), fg=self.c_cyan, bg=self.c_card,
            bd=1, relief="solid", highlightbackground=self.c_border
        )
        card.pack(fill="both", expand=True, padx=4, pady=4)

        rec_box = tk.Frame(card, bg="#1a1b24", highlightbackground=self.c_border, highlightthickness=1)
        rec_box.pack(fill="x", padx=8, pady=6)

        self.adv_build_name = tk.Label(rec_box, text="Recommended: Goblin Research (R24)", font=("Segoe UI", 10, "bold"), fg=self.c_gold, bg="#1a1b24")
        self.adv_build_name.pack(anchor="w", padx=8, pady=(6, 2))

        self.adv_build_meta = tk.Label(rec_box, text="Faction: Goblin | Bloodline: Druid | Bracket: 1e72 - 1e99 Gems", font=("Segoe UI", 8), fg=self.c_cyan, bg="#1a1b24")
        self.adv_build_meta.pack(anchor="w", padx=8, pady=1)

        self.adv_build_notes = tk.Label(rec_box, text="Notes: Pushes to 1e99 gems to trigger Reincarnation 25.", font=("Segoe UI", 8), fg=self.c_text, bg="#1a1b24", wraplength=520, justify="left")
        self.adv_build_notes.pack(anchor="w", padx=8, pady=(1, 6))

        self.visible_input_var=tk.BooleanVar(value=not load_config().get('require_minimized',True))
        tk.Checkbutton(card,text='Allow background messages while the game remains visible (never take focus)',
            variable=self.visible_input_var,command=self.save_selected_path,bg=self.c_card,fg=self.c_text,
            selectcolor=self.c_panel,font=('Segoe UI',8)).pack(anchor='w',padx=8,pady=3)
        self.route_detail=tk.Label(card,text='Next prerequisite: reading state',bg=self.c_card,fg=self.c_amber,
            wraplength=550,justify='left',font=('Segoe UI',8))
        self.route_detail.pack(fill='x',padx=8,pady=4)

        lbl_tmpl = tk.Label(card, text="Build Template Code:", font=("Segoe UI", 8, "bold"), fg=self.c_muted, bg=self.c_card)
        lbl_tmpl.pack(anchor="w", padx=8, pady=(4, 1))

        self.template_text = tk.Text(card, height=4, font=("Consolas", 8), bg="#14161f", fg=self.c_cyan, bd=1, relief="solid", highlightbackground=self.c_border)
        self.template_text.pack(fill="x", padx=8, pady=(0, 6))

        btn_row = tk.Frame(card, bg=self.c_card)
        btn_row.pack(fill="x", padx=8, pady=4)

        copy_btn = tk.Button(
            btn_row, text="📋 Copy Template", font=("Segoe UI", 8, "bold"),
            bg="#2c3e50", fg="white", activebackground="#34495e", activeforeground="white",
            relief="flat", padx=10, pady=4, cursor="hand2", command=self.action_copy_template
        )
        copy_btn.pack(side="left", padx=(0, 6))
        self.bind_hover(copy_btn, "Copy Template: Copies the active build template code to the system clipboard.")

        apply_btn = tk.Button(
            btn_row, text="🚀 1-Click Deploy to Live Game", font=("Segoe UI", 8, "bold"),
            bg="#1b6ca8", fg="white", activebackground="#2980b9", activeforeground="white",
            relief="flat", padx=10, pady=4, cursor="hand2", command=self.action_apply_build
        )
        apply_btn.pack(side="left")
        self.bind_hover(apply_btn, "1-Click Deploy: Enters the template through normal game UI and checks actual upgrade ownership.")

        db_card = tk.LabelFrame(
            card, text=" Scraped Wiki Progression Builds Matrix ",
            font=("Segoe UI", 8, "bold"), fg=self.c_gold, bg=self.c_card,
            bd=1, relief="solid", highlightbackground=self.c_border
        )
        db_card.pack(fill="both", expand=True, padx=4, pady=6)

        self.builds_listbox = tk.Listbox(db_card, font=("Segoe UI", 8), bg="#14161f", fg=self.c_text, selectbackground="#2c3e50", selectforeground=self.c_cyan, bd=0)
        self.builds_listbox.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self.builds_listbox.bind("<<ListboxSelect>>", self.on_build_selected)

        scrollbar = tk.Scrollbar(db_card, orient="vertical", command=self.builds_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.builds_listbox.config(yscrollcommand=scrollbar.set)

        for bkey, bval in BUILDS_DATABASE.items():
            self.builds_listbox.insert("end", f"[{bkey}] {bval['name']}")


    def inspect_named_goal(self):
        from src.knowledge_service import KnowledgeService
        from tkinter import messagebox
        try:
            service=KnowledgeService()
            plan=service.plan_target(self.named_goal_var.get(),get_live_game_state())
            lines=[plan['goal']+' - '+('OWNED' if plan['complete'] else 'prerequisite plan')]
            for step in plan['steps']:
                lines.append(f"{step['status']}: {step['name']}")
                for cost in step.get('costs',[]):
                    lines.append(f"  {cost['field']}: have {cost.get('actual')}, need {cost.get('amount')}")
                for condition in step.get('conditions',[]):
                    if condition['satisfied'] is not True:lines.append('  Missing: '+str(condition.get('field',condition.get('text','unparsed requirement'))))
            coverage=service.coverage()
            lines.append(f"\nKnowledge: {coverage['reference_cards']} reference cards; {coverage['reviewed_recipes']} reviewed recipes. References are not all executable.")
            messagebox.showinfo('Source-backed goal requirements','\n'.join(lines),parent=self.root)
        except Exception as exc:self.set_feedback(str(exc),self.c_red)

    def save_selected_path(self):
        config=load_config()
        config['selected_path']=self.path_var.get()
        config['selected_goal']=self.goal_var.get()
        if hasattr(self,'named_goal_var'):config['named_goal']=self.named_goal_var.get().strip()
        if hasattr(self,'visible_input_var'):
            config['require_minimized']=not self.visible_input_var.get()
        if config['selected_goal']=='Next reincarnation' and 'goal_target_r' not in config:
            config['goal_target_r']=get_live_game_state()['reincarnation']+1
        save_config(config)
        self.config=config
        self.set_feedback('Selected path saved. Existing pause state was preserved.')
        self.update_state()

    def start_selected_path(self):
        try:
            require_interactive_session()
        except Exception as exc:
            self.set_feedback(f'Start blocked: {exc}',self.c_red)
            return False
        try:
            self.save_selected_path()
        except Exception as exc:
            self.set_feedback(f'Start blocked while saving goal settings: {exc}',self.c_red)
            return False
        try:
            state=get_live_game_state()
        except Exception as exc:
            self.set_feedback(f'Start blocked: could not read current game state ({exc}).',self.c_red)
            return False
        if not state.get('telemetry',{}).get('process_connected'):
            self.set_feedback('Start blocked: Realm Grinder is not connected on this desktop.',self.c_red)
            return False
        config=load_config()
        try:
            if config.get('require_minimized',True) and not self.clearer.window.is_minimized():
                self.set_feedback('Enable visible-window input in Build Advisor, or minimize the game for mapped actions.',self.c_amber)
                return False
        except Exception as exc:
            self.set_feedback(f'Start blocked: game window could not be validated ({exc}).',self.c_amber)
            return False
        pending_path=os.path.join(os.path.dirname(STATE_FILE),'pending_action.json')
        if os.path.exists(pending_path):
            try:
                with open(pending_path,encoding='utf-8') as pending_file:
                    pending=json.load(pending_file)
                if not isinstance(pending,dict) or not isinstance(pending.get('status'),str):
                    raise ValueError('pending action record has no valid status')
            except (OSError,ValueError,TypeError) as exc:
                self.set_feedback(f'Start blocked: pending action record is unreadable ({exc}).',self.c_amber)
                return False
            if pending.get('status') in ('UNCERTAIN','DISPATCHED'):
                from src.action_verification import reconcile_known_template_no_text
                try:
                    reconciled=reconcile_known_template_no_text(pending_path,state)
                except Exception as exc:
                    self.set_feedback(f'Start blocked: pending action could not be reconciled ({exc}).',self.c_amber)
                    return False
                if reconciled:
                    self.set_feedback('Recorded the old template attempt as no text sent. Review goal settings, then click Start again.',self.c_amber)
                    messagebox.showinfo('Template attempt reconciled',
                        'The recorded error occurred before the template text field was clicked or any characters were typed. '
                        'The original transaction and backup were retained. The bot is still paused; review the selected goal, then click Start again.',
                        parent=self.root)
                    return False
                try:
                    with open(pending_path,encoding='utf-8') as pending_file:
                        pending=json.load(pending_file)
                    if not isinstance(pending,dict) or not isinstance(pending.get('status'),str):
                        raise ValueError('pending action record has no valid status')
                except (OSError,ValueError,TypeError) as exc:
                    self.set_feedback(f'Start blocked: pending action record is unreadable ({exc}).',self.c_amber)
                    return False
                if pending.get('status') not in ('UNCERTAIN','DISPATCHED'):
                    # Another process reconciled it while this handler was running.
                    pass
                else:
                    self.set_feedback(f"Reconciliation required: {pending.get('action','unknown action')} ({pending.get('status')}).",self.c_amber)
                    messagebox.showwarning('Resume blocked: unresolved action',pending_action_summary(pending),parent=self.root)
                    return False
            elif pending.get('status') not in ('VERIFIED','NO_EFFECT','RECONCILED_NO_TEMPLATE_TEXT'):
                self.set_feedback(f"Start blocked: unrecognized pending action status ({pending.get('status')}).",self.c_amber)
                return False
        if config.get('selected_goal')=='Build only' and config.get('named_goal') in ('Reach R46','Dragon Tamer'):
            self.set_feedback('Build only pauses after the current build is verified; explicit target tracking is available under Named goal.',self.c_amber)
        config['paused']=False
        if config.get('selected_goal')=='Next reincarnation':config['goal_target_r']=state['reincarnation']+1
        save_config(config)
        if os.path.exists(STOP_FILE):os.remove(STOP_FILE)
        self.config=config
        message='Selected path started. The existing worker will execute one verified prerequisite at a time.'
        if config.get('selected_goal')=='Build only' and config.get('named_goal') in ('Reach R46','Dragon Tamer'):
            message+=' Build only pauses if the active build becomes verified; select Named goal for explicit '+config['named_goal']+' tracking.'
            self.set_feedback(message,self.c_amber)
        else:self.set_feedback(message,self.c_cyan)
        self.update_state()
        return True

    def on_build_selected(self, event):
        sel = self.builds_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        bkeys = list(BUILDS_DATABASE.keys())
        if idx < len(bkeys):
            bdata = BUILDS_DATABASE[bkeys[idx]]
            self.template_text.delete("1.0", "end")
            self.template_text.insert("1.0", bdata["template"])

    def action_copy_template(self):
        tmpl = self.template_text.get("1.0", "end").strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(tmpl)
        self.set_feedback("Template code copied to clipboard!")
        messagebox.showinfo("Copied", "Template copied to clipboard!")

    def action_apply_build(self):
        template=self.template_text.get('1.0','end').strip()
        if not template:return
        if not input_allowed(self.clearer.window):
            self.set_feedback('Start the selected path before sending a template; pause and window guards are active.',self.c_amber)
            return
        def work():
            try:
                result=self.bot.actions.deploy_template(template)
                self.set_feedback(result['status']+': '+result['message'],self.c_green if result['success'] else self.c_amber)
            except Exception as exc:self.set_feedback('Template error: '+str(exc),self.c_red)
        threading.Thread(target=work,daemon=True).start()

    def build_tab_wiki(self):
        card = tk.LabelFrame(
            self.tab_wiki, text=" G00F Not-a-Wiki Searchable Encyclopedia ",
            font=("Segoe UI", 8, "bold"), fg=self.c_gold, bg=self.c_card,
            bd=1, relief="solid", highlightbackground=self.c_border
        )
        card.pack(fill="both", expand=True, padx=4, pady=4)

        search_row = tk.Frame(card, bg=self.c_card)
        search_row.pack(fill="x", padx=8, pady=6)

        lbl = tk.Label(search_row, text="Lookup Code / Name:", font=("Segoe UI", 8, "bold"), fg=self.c_cyan, bg=self.c_card)
        lbl.pack(side="left", padx=(0, 6))

        self.wiki_search_entry = tk.Entry(search_row, font=("Segoe UI", 9), bg="#14161f", fg=self.c_text, insertbackground="white", bd=1, relief="solid")
        self.wiki_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.wiki_search_entry.bind("<Return>", lambda e: self.action_wiki_search())

        search_btn = tk.Button(
            search_row, text="🔍 Search", font=("Segoe UI", 8, "bold"),
            bg="#2c3e50", fg="white", activebackground="#34495e", activeforeground="white",
            relief="flat", padx=8, pady=2, cursor="hand2", command=self.action_wiki_search
        )
        search_btn.pack(side="left")

        chips_row = tk.Frame(card, bg=self.c_card)
        chips_row.pack(fill="x", padx=8, pady=(0, 6))

        sample_chips = ["S50", "E290", "A105", "D55", "W25", "Leet", "Harlequin", "Egg", "Dragon Tamer"]
        for c in sample_chips:
            btn = tk.Button(
                chips_row, text=c, font=("Segoe UI", 7),
                bg="#1a1b24", fg=self.c_muted, relief="flat", padx=4, pady=1,
                command=lambda val=c: self.quick_chip_search(val)
            )
            btn.pack(side="left", padx=2)

        self.wiki_result_text = tk.Text(
            card, font=("Segoe UI", 8), bg="#14161f", fg=self.c_text,
            bd=1, relief="solid", highlightbackground=self.c_border, wrap="word"
        )
        self.wiki_result_text.pack(fill="both", expand=True, padx=8, pady=4)

        self.wiki_result_text.insert(
            "1.0",
            "📖 G00F Not-a-Wiki Local Knowledge Base\n\n"
            "Search across 252 Researches and 109 Trophies scraped directly from musicfamily.org/realm/.\n\n"
            "Try searching:\n"
            "• 'S50' or 'Conjuration' (Goblin Research)\n"
            "• 'E290' (Excavation synergy)\n"
            "• 'Leet' or 'Unitary' (Secret Trophies)\n"
            "• 'Dragon Tamer' or 'Egg' (Unlock details)\n"
        )

    def quick_chip_search(self, term: str):
        self.wiki_search_entry.delete(0, "end")
        self.wiki_search_entry.insert(0, term)
        self.action_wiki_search()

    def action_wiki_search(self):
        query=self.wiki_search_entry.get().strip()
        if not query:return
        store=KnowledgeStore();rows=store.search(query,limit=5);stats=store.stats()
        output=[f"Local reference: {stats['documents']} source pages, {stats['records']} reference blocks, {stats['templates']} templates.",
                'Source prose is not automatically an executable prerequisite. Installed-version differences are explicit.','']
        for row in rows:
            output += [row['title'],f"Source: {row['source_url']}",f"Retrieved source: {row['resolved_url']}",
                       f"Archive capture: {row['captured_at'] or 'Not an archived capture / date not established'}",'']
            text=row['text'];position=text.lower().find(query.lower())
            if position<0:position=0
            output += [text[max(0,position-250):position+4500],'\n'+'-'*60+'\n']
        if not rows:output.append('No indexed match. The absence of a result is not evidence that the requirement does not exist.')
        self.wiki_result_text.delete('1.0','end')
        self.wiki_result_text.insert('1.0','\n'.join(output))

    def build_tab_controls(self):
        card = tk.LabelFrame(
            self.tab_controls, text=" Flippable Automation Controls & Parameters ",
            font=("Segoe UI", 8, "bold"), fg=self.c_cyan, bg=self.c_card,
            bd=1, relief="solid", highlightbackground=self.c_border
        )
        card.pack(fill="both", expand=True, padx=4, pady=4)

        self.toggle_vars = {}
        toggles = [
            ("auto_reincarnate", "Auto Reincarnate (when target gems reached)", False),
            ("auto_abdicate", "Auto Abdicate (on significant gem increase)", False),
            ("auto_spells", "Auto Spell Combo & Autocast Loop (keys 1-6)", True),
            ("auto_buy_buildings", "Auto Buy All Buildings", True),
            ("auto_buy_upgrades", "Auto Buy All Upgrades", True),
            ("auto_excavate", "Auto Smart Excavations (R46 Egg hunt)", False),
            ("auto_click_realm", "Auto Click Realm Background", True),
            ("auto_apply_build", "Auto Deploy Recommended Wiki Build", True),
            ("ultron_burst", "⚡ UltronBurst Protocol (First-Principles Renaissance)", True)
        ]

        for key, text, def_val in toggles:
            val = self.config.get(key, def_val)
            var = tk.BooleanVar(value=val)
            self.toggle_vars[key] = var
            cb = tk.Checkbutton(
                card, text=text, variable=var, font=("Segoe UI", 8),
                fg=self.c_text, bg=self.c_card, selectcolor="#14161f",
                activebackground=self.c_card, activeforeground=self.c_cyan,
                command=lambda k=key, v=var: self.on_toggle_changed(k, v)
            )
            cb.pack(anchor="w", padx=12, pady=3)

        param_frame = tk.Frame(card, bg=self.c_card)
        param_frame.pack(fill="x", padx=12, pady=8)

        lbl_mult = tk.Label(param_frame, text="Abdication Gem Multiplier:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_card)
        lbl_mult.grid(row=0, column=0, sticky="w", pady=2)

        self.mult_entry = tk.Entry(param_frame, font=("Segoe UI", 8), width=8, bg="#14161f", fg=self.c_text, insertbackground="white", bd=1, relief="solid")
        self.mult_entry.insert(0, str(self.config.get("abdicate_multiplier_threshold", 50.0)))
        self.mult_entry.grid(row=0, column=1, sticky="w", padx=8, pady=2)

        lbl_delay = tk.Label(param_frame, text="Bot Cycle Delay (sec):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_card)
        lbl_delay.grid(row=1, column=0, sticky="w", pady=2)

        self.delay_entry = tk.Entry(param_frame, font=("Segoe UI", 8), width=8, bg="#14161f", fg=self.c_text, insertbackground="white", bd=1, relief="solid")
        self.delay_entry.insert(0, str(self.config.get("cycle_delay_sec", 3.0)))
        self.delay_entry.grid(row=1, column=1, sticky="w", padx=8, pady=2)

        save_params_btn = tk.Button(
            param_frame, text="💾 Save Parameters", font=("Segoe UI", 8, "bold"),
            bg="#2c3e50", fg="white", activebackground="#34495e", activeforeground="white",
            relief="flat", padx=8, pady=2, command=self.action_save_params
        )
        save_params_btn.grid(row=2, column=0, columnspan=2, sticky="w", pady=6)

    def action_save_params(self):
        try:
            m = float(self.mult_entry.get())
            d = float(self.delay_entry.get())
            self.config["abdicate_multiplier_threshold"] = m
            self.config["cycle_delay_sec"] = d
            save_config(self.config)
            self.set_feedback("Bot parameters saved and synchronized!")
            messagebox.showinfo("Saved", "Bot parameters successfully updated and persisted!")
        except ValueError:
            messagebox.showerror("Error", "Invalid numeric values entered.")

    def on_toggle_changed(self, key: str, var: tk.BooleanVar):
        val = var.get()
        self.config[key] = val
        update_setting(key, val)
        self.set_feedback(f"Automation setting '{key}' toggled to {val}.")

    def build_tab_logs(self):
        card = tk.LabelFrame(
            self.tab_logs, text=" Live Execution Logs & Bot Telemetry ",
            font=("Segoe UI", 8, "bold"), fg=self.c_gold, bg=self.c_card,
            bd=1, relief="solid", highlightbackground=self.c_border
        )
        card.pack(fill="both", expand=True, padx=4, pady=4)

        self.log_text = tk.Text(card, font=("Consolas", 8), bg="#14161f", fg=self.c_text, bd=0)
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

        btn_row = tk.Frame(card, bg=self.c_card)
        btn_row.pack(fill="x", padx=4, pady=2)

        clear_btn = tk.Button(
            btn_row, text="Clear Log View", font=("Segoe UI", 7),
            bg="#2c303d", fg=self.c_muted, relief="flat", padx=6, pady=2,
            command=lambda: self.log_text.delete("1.0", "end")
        )
        clear_btn.pack(side="left")

    # =========================================================================
    # INTERACTIVE GATE CLEARANCE ACTIONS
    # =========================================================================
    def action_auto_clear_active(self):
        self.start_selected_path()

    def action_fast_track(self):
        self.start_selected_path()

    def action_clear_reincarnation(self):
        self.start_selected_path()

    def action_manual_abdicate(self):
        """Triggers safe abdication to claim potential gems."""
        if self.is_clearing_gate:
            return
        self.is_clearing_gate = True
        self.set_feedback("💫 Abdicating to compound gems...", self.c_gold)

        def _worker():
            try:
                st = get_live_game_state()
                pot = st["potential_gems"]
                from src.state_machine import DragonBot
                bot = DragonBot()
                bot.perform_abdication(pot)
                self.set_feedback(f"✓ Abdication complete! Claimed +{pot:.2e} gems.", self.c_green)
            except Exception as e:
                self.set_feedback(f"Abdication Error: {e}", self.c_red)
            finally:
                self.is_clearing_gate = False
                self.root.after(200, self.update_state)

        threading.Thread(target=_worker, daemon=True).start()

    def action_manual_reincarnate(self):
        """Triggers reincarnation if requirements are met."""
        if self.is_clearing_gate:
            return
        st = get_live_game_state()
        r = st["reincarnation"]
        gems = st["gems"]
        req = get_reincarnation_gem_requirement(r)

        if gems < req:
            messagebox.showwarning("Not Ready", f"Cannot reincarnate to R{r+1} yet!\nCurrent Gems: {gems:.2e}\nRequired Gems: {req:.2e}")
            return

        self.is_clearing_gate = True
        self.set_feedback(f"🔄 Reincarnating to R{r+1}...", self.c_gold)

        def _worker():
            try:
                from src.state_machine import DragonBot
                bot = DragonBot()
                bot.perform_reincarnation(r, gems, req)
                self.set_feedback(f"🎉 Successfully Reincarnated to R{r+1}!", self.c_green)
            except Exception as e:
                self.set_feedback(f"Reincarnate Error: {e}", self.c_red)
            finally:
                self.is_clearing_gate = False
                self.root.after(200, self.update_state)

        threading.Thread(target=_worker, daemon=True).start()

    def action_clear_gate(self, stage_id: int):
        """Executes targeted clearance routine for the specified stage ID."""
        if self.is_clearing_gate:
            return
        self.is_clearing_gate = True
        self.set_feedback(f"⚡ Executing manual action for Stage {stage_id}...", self.c_gold)

        def _worker():
            try:
                if stage_id == 0:
                    res = self.clearer.clear_excavation_gate(1500)
                elif stage_id == 1:
                    res = self.clearer.clear_hatch_gate()
                elif stage_id == 2:
                    res = self.clearer.clear_drakeling_gate()
                elif stage_id == 3:
                    res = self.clearer.clear_dragon_gate()
                elif stage_id == 4:
                    res = self.clearer.clear_elder_dragon_gate()
                else:
                    res = {"success": False, "message": f"Unknown stage {stage_id}"}

                msg = res.get("message", f"Stage {stage_id} action executed.")
                color = self.c_green if res.get("success", False) else self.c_red
                self.set_feedback(f"✓ {msg}", color)
            except Exception as e:
                self.set_feedback(f"Stage {stage_id} Error: {e}", self.c_red)
            finally:
                self.is_clearing_gate = False
                self.root.after(200, self.update_state)

        threading.Thread(target=_worker, daemon=True).start()

    def action_backup(self):
        try:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            p = os.path.join(BACKUP_DIR, f"realm-grinder-export-{ts}.txt")
            with open(p, "w") as f:
                f.write(extract_save_string_from_sol())
            self.set_feedback(f"Save safely backed up: {os.path.basename(p)}")
            messagebox.showinfo("Backup Success", f"Save safely backed up to:\n{p}")
        except Exception as e:
            messagebox.showerror("Backup Error", f"Failed: {e}")

    def action_snapshot_state(self):
        def _snap():
            try:
                self.set_feedback("Capturing state and screenshot (minimized-safe)...", self.c_cyan)
                from src.state_capture import StateCaptureEngine
                engine = StateCaptureEngine()
                snap = engine.capture_full_state(save_screenshot=True)
                shot_name = os.path.basename(snap["metadata"]["screenshot_path"])
                self.set_feedback(f"✓ Snapshot saved: {shot_name} & JSON telemetry.", self.c_green)
                messagebox.showinfo(
                    "State Snapshot Captured",
                    f"Full Game State & Screenshot successfully captured!\n\n"
                    f"Screenshot:\n{snap['metadata']['screenshot_path']}\n\n"
                    f"Save Backup:\n{snap['metadata']['backup_path']}\n\n"
                    f"Telemetry JSON:\nstate/latest_state_capture.json"
                )
            except Exception as e:
                self.set_feedback(f"Snapshot Error: {e}", self.c_red)

        threading.Thread(target=_snap, daemon=True).start()

    def action_toggle_pause(self):
        config=load_config()
        is_paused=os.path.exists(STOP_FILE) or config.get('paused',True)
        if is_paused:
            # Resume must pass the same connection, geometry and pending-action checks as Start.
            self.start_selected_path()
            return
        with open(STOP_FILE,'w',encoding='utf-8') as output:output.write('Paused by user')
        config['paused']=True;save_config(config);self.config=config
        self.pause_btn.configure(text='Resume Bot',bg='#1b6ca8')
        self.worker_badge.configure(text='Bot paused',fg=self.c_amber)
        self.set_feedback('Bot paused. In-game autocasting is a separate game setting.')

    def action_automate_straight_to_goal(self):
        """1-Click 'Automate Straight to Goal' handler.

        Delegates all admission and resume state changes to Start/Resume, then
        applies the existing non-focus-stealing window hint and updates the HUD.

        Safety constraints: READ-ONLY memory only; one worker owner (WorkerLease);
        never steals focus or restores minimized state.
        """
        try:
            started = self.start_selected_path()
        except Exception as exc:
            self.set_feedback(f'Automate blocked: {exc}', self.c_red)
            return False
        if not started:
            if hasattr(self, 'automate_status_lbl'):
                self.automate_status_lbl.configure(
                    text='⛔ Not started | Start admission checks blocked automation.',
                    fg=self.c_amber
                )
            return False

        # Show game window in background (non-intrusive) if it is findable
        try:
            hwnd = self.clearer.window.hwnd
            if not hwnd or not win32gui.IsWindow(hwnd):
                self.clearer.window.find_window()
                hwnd = self.clearer.window.hwnd
            if hwnd and win32gui.IsWindow(hwnd) and win32gui.IsIconic(hwnd):
                # SW_SHOWNOACTIVATE = 4: shows without taking focus or un-minimizing
                # Only show if already minimized; do NOT restore a user-minimized window.
                pass  # respect current minimized state; AIR still runs at full speed
            elif hwnd and win32gui.IsWindow(hwnd):
                # Window is visible — ensure it stays in background, no focus theft
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
        except Exception:
            pass  # window state management is best-effort; never block automation for it

        # Load config, set goal and unpause
        config = load_config()
        goal = config.get('selected_goal', 'Dragon Tamer')
        named = config.get('named_goal', 'Dragon Tamer')
        goal_display = named if goal == 'Named goal' else goal

        self.config = config

        # Update feedback and automate button label
        msg = f'🚀 Automating straight to {goal_display}: Autonomous progression active.'
        self.set_feedback(msg, self.c_gold)
        if hasattr(self, 'automate_status_lbl'):
            self.automate_status_lbl.configure(
                text=f'🚀 Active → {goal_display} | Worker running. Pause Bot to stop.',
                fg=self.c_green
            )
        self.update_state()
        return True

    def update_mana_bar(self):
        """Refresh the live volatile mana bar at 250ms intervals without blocking the UI thread."""
        try:
            if self.root.winfo_exists():
                st = get_live_game_state()
                bar = mana_bar(st)
                health = st.get('telemetry', {}).get('memory_provider_health', 'UNKNOWN')
                is_live = bar['is_live'] and health == 'HEALTHY'

                # [MEM] badge color: cyan-glow when live memory active, muted otherwise
                badge_color = '#00e5c0' if is_live else self.c_muted
                badge_bg = '#0a2020' if is_live else '#0e1520'
                badge_text = '[MEM]' if is_live else '[SAV]'
                self.mem_badge.configure(text=badge_text, fg=badge_color, bg=badge_bg)

                # Mana label and progress bar
                cur = bar['current_str']
                mx = bar['maximum_str']
                regen = bar['regen_str']
                saturating = (bar.get('fill_pct') or 0) >= 95.0
                label_color = '#ff8c42' if saturating else (self.c_cyan if is_live else self.c_muted)
                self.mana_label.configure(
                    text=f'Mana: {cur} / {mx} | Regen: {regen}/s',
                    fg=label_color
                )
                fill = bar['fill_pct'] if bar['fill_pct'] is not None else 0
                self.mana_bar_prog['value'] = fill

                # Source badge on right
                self.mem_source_lbl.configure(text=bar['source_badge'], fg=badge_color)
        except Exception:
            pass
        finally:
            try:
                if self.root.winfo_exists():
                    self.root.after(250, self.update_mana_bar)
            except Exception:
                pass

    def action_force_refresh(self):
        self.update_state()
        self.set_feedback("Live save state refreshed from disk.")



    def update_state(self):
        try:
            st = get_live_game_state()
            r = st["reincarnation"]
            gems = st["gems"]
            coins = st["coins"]
            coins_this_game = st.get("coins_this_game", coins)
            excavations = st["excavations"]
            hellfire = st.get("hellfire_time", 0)
            has_egg = st["has_egg"]
            assistants=st.get("fairy_assistants")
            mana=st.get("mana_max")
            build_status=self.clearer.actions.diagnose_build(st)

            # Potential gems calculation
            pot_gems = math.floor((math.sqrt(1.0 + 8.0 * (coins_this_game / 1e12)) - 1.0) / 2.0) if coins_this_game > 0 else 0.0
            req_gems = get_reincarnation_gem_requirement(r)

            # Telemetry ETAs
            stage_timestamps = {}
            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, "r") as sf:
                        stage_timestamps = json.load(sf).get("timestamps", {})
                except Exception:
                    pass

            etas = self.telemetry.calculate_etas(r, gems, coins, stage_timestamps, hellfire_time=hellfire,reload_history=True)

            # Update Header Overall ETA and R46 Badge
            self.overall_eta_lbl.configure(text=f"ETA: {etas['total_eta']}")
            self.overall_target_lbl.configure(text=etas['target_completion_date'] or "")
            self.r46_eta_badge.configure(text=f"R46 ETA: ~{etas['r46_eta']}")
            self.hf_lbl.configure(text=telemetry_banner(st,build_status))

            # Dynamic Pause State Sync
            cfg = load_config()
            is_paused = os.path.exists(STOP_FILE) or cfg.get("paused", False)
            if is_paused:
                self.pause_btn.configure(text="▶ Resume Bot", bg="#1b6ca8")
                self.worker_badge.configure(text="● Bot Paused", fg=self.c_amber, bg="#261b0a")
            else:
                self.pause_btn.configure(text="⏸ Pause Bot", bg="#8b2626")
                self.worker_badge.configure(text="🤖 24/7 Autopilot", fg=self.c_green, bg="#0d2218")

            # Live Window Minimized State Sync
            try:
                hwnd = self.clearer.window.hwnd
                if not hwnd or not win32gui.IsWindow(hwnd):
                    self.clearer.window.find_window()
                    hwnd = self.clearer.window.hwnd
                if hwnd and win32gui.IsWindow(hwnd):
                    if win32gui.IsIconic(hwnd):
                        self.window_state_badge.configure(text="🗕 Minimized", fg=self.c_cyan, bg="#0c202a")
                    else:
                        self.window_state_badge.configure(text="🗖 Visible", fg=self.c_muted, bg=self.c_panel)
            except Exception:
                pass

            # Skynet AI, Guardian, and Monte Carlo evaluation
            ai_eval = self.ai.evaluate(st, cfg)
            pulse={'game_alive':st.get('telemetry',{}).get('process_connected',False),'save_hash':None,'restarts':0}
            mc = MonteCarloArtifactForecaster.calculate_egg_probabilities(excavations,current_r=r)

            # Update Quest tab Skynet AI Live Banner
            self.skynet_banner_lbl.configure(
                text=f"🧠 SKYNET AI DIRECTIVE: {ai_eval['decision']} | {ai_eval['reasoning'][:90]}..."
            )

            # Update Skynet Tab Widgets
            self.skynet_directive_badge.configure(text=f"⚡ DIRECTIVE: {ai_eval['decision']}")
            self.skynet_priority_badge.configure(text=f"Priority: {ai_eval['priority']} / 100")
            self.skynet_thought_text.delete("1.0", "end")
            self.skynet_thought_text.insert("1.0", ai_eval["reasoning"])

            is_ub = bool(cfg.get("ultron_burst", True))
            if is_ub:
                self.ultron_burst_badge.configure(text="⚡ ULTRONBURST: ENGAGED", fg=self.c_gold, bg="#1e180a")
                self.ultron_badge.configure(text="⚡ ULTRONBURST: ENGAGED", fg=self.c_gold, bg="#1e180a")
            else:
                self.ultron_burst_badge.configure(text="⚡ ULTRONBURST: STANDBY", fg=self.c_muted, bg=self.c_card)
                self.ultron_badge.configure(text="⚡ ULTRONBURST: STANDBY", fg=self.c_muted, bg=self.c_panel)

            payload = ai_eval.get("payload", {})
            vel = payload.get("velocity", 0.0)
            sat = payload.get("saturation", 0.0)
            elapsed = payload.get("elapsed", 0.0)

            self.skynet_sat_bar["value"] = sat * 100.0
            sat_status = "Plateau / Inflection Near" if sat > 0.7 else "Accelerating Growth"
            self.skynet_sat_pct_lbl.configure(text=f"{sat*100.0:.1f}% ({sat_status})")
            self.skynet_vel_lbl.configure(text=f"Gem Velocity (dG/dt): +{format_rg_num(vel)} /s")
            self.skynet_elapsed_lbl.configure(text=f"Current Run Duration: {int(elapsed//60)}m {int(elapsed%60):02d}s")

            # Monte Carlo widget update
            elig_str = "Eligible now!" if mc["is_eligible"] else "Unlocks at 1500 digs in R46"
            self.mc_chance_lbl.configure(text=f"Drop Chance per Dig: {mc['current_dig_drop_percent']:.4f}% ({elig_str})")
            self.mc_p50_lbl.configure(text=f"P50 (Median Drop): ~{mc['p50_digs_needed']} digs past 1500")
            self.mc_p90_lbl.configure(text=f"P90 (90% Confidence): ~{mc['p90_digs_needed']} digs")
            self.mc_p99_lbl.configure(text=f"P99 (model estimate): ~{mc['p99_digs_needed']} digs")

            # Guardian status update
            g_alive = pulse.get("game_alive", True)
            self.g_status_lbl.configure(
                text=f"Game process: {'CONNECTED' if g_alive else 'NOT CONNECTED'}",
                fg=self.c_green if g_alive else self.c_amber
            )
            h_str = pulse.get("save_hash", "") or ""
            if len(h_str) >= 14:
                self.g_hash_lbl.configure(text=f"Save SHA256: {h_str[:8]}...{h_str[-6:]} (Verified)")
            self.g_restarts_lbl.configure(text=f"Auto-Heal Crashes: {pulse.get('restarts', 0)}")

            # 1. Update Active Bottleneck Banner
            if r < 46:
                pct_gem = min(100.0, (gems / req_gems) * 100.0)
                self.active_gate_lbl.configure(text=f"⚡ Active Bottleneck: Gate 0 (Reincarnation R{r} -> R{r+1})")
                self.active_gate_sublbl.configure(
                    text=f"Target: {format_rg_num(req_gems)} ({pct_gem:.1f}%) | Missing: {46-r} R's | Next R: ~{etas['current_r_eta']}"
                )
            elif not has_egg:
                self.active_gate_lbl.configure(text="⚡ Active Bottleneck: Gate 1 (Spiky Rough Egg Artifact 211)")
                rem_excav = max(0, 1500 - excavations)
                self.active_gate_sublbl.configure(
                    text=f"Excavations: {excavations}/1,500 ({rem_excav} remaining). 2% drop rate past 1500."
                )
            else:
                self.active_gate_lbl.configure(text="⚡ Active Bottleneck: Dragon Unlock Quest in Progress")
                self.active_gate_sublbl.configure(text=f"Stages 1-4 incubating / fulfilling requirements. Overall ETA: {etas['total_eta']}")

            # 2. Update Gate 0 (Reincarnation) Card
            pct_r = min(100.0, (r / 46.0) * 100.0)
            self.r_val_lbl.configure(text=f"Reincarnation: R{r} / R46 ({pct_r:.1f}%)")
            self.r_prog["value"] = pct_r
            self.gems_lbl.configure(text=f"Gems: {format_rg_num(gems)}")
            self.pot_gems_lbl.configure(text=f"Pot Gems: {format_rg_num(pot_gems)}")
            self.coins_lbl.configure(text=f"Coins: {format_rg_num(coins)}")
            self.goal_lbl.configure(text=f"R{r+1} Goal: {format_rg_num(req_gems)} (ETA: {etas['current_r_eta']})")

            # Update Reincarnate button state
            if gems >= req_gems:
                self.btn_reincarnate.configure(state="normal", bg=self.c_green, fg="#0d1117", text=f"🟢 REINCARNATE TO R{r+1} (READY!)")
                self.bind_hover(self.btn_reincarnate, f"Reincarnate: Ready now! Current gems exceed required threshold for R{r+1}.")
            else:
                self.btn_reincarnate.configure(state="disabled", bg=self.c_dark, fg=self.c_muted, text="🔒 Reincarnate (Need More Gems)")
                self.bind_hover(self.btn_reincarnate, f"Reincarnate Locked: Current gems {format_rg_num(gems)} / {format_rg_num(req_gems)}.")

            # 3. Update Dragon Unlock Stages Breakdown
            # Stage 0: Egg
            card0 = self.stage_cards[0]
            if has_egg:
                card0["status_lbl"].configure(text="COMPLETED ✓", fg=self.c_green)
                card0["prog_lbl"].configure(text="Egg Acquired! Artifact 211 unlocked in save.", fg=self.c_green)
                card0["prog_bar"]["value"] = 100
                card0["clear_btn"].configure(text="🟢 Egg Acquired ✓", state="disabled", bg=self.c_dark, fg=self.c_muted)
                self.bind_hover(card0["clear_btn"], "Stage 0 Complete: Spiky Rough Egg is already found and verified in your save.")
            else:
                if r < 46:
                    card0["status_lbl"].configure(text=f"LOCKED (Current R{r}, Need R46)", fg=self.c_muted)
                    card0["prog_lbl"].configure(text=f"Excavations: {excavations}/1500 | Reincarnation: R{r}/R46 | R46 ETA: ~{etas['r46_eta']}", fg=self.c_muted)
                    card0["prog_bar"]["value"] = min(100.0, (r / 46.0) * 100.0)
                    card0["clear_btn"].configure(text="🟣 Fast-Track R46 Climb", state="normal", bg=self.c_purple, fg="white")
                    self.bind_hover(card0["clear_btn"], "Fast-Track Climb: (Manual override) Pushes production and build deployment to advance towards R46.")
                else:
                    rem = max(0, 1500 - excavations)
                    card0["status_lbl"].configure(text="READY TO CLEAR ⚡", fg=self.c_gold)
                    card0["prog_lbl"].configure(text=f"Excavations: {excavations}/1500 ({rem} remaining) | Dig ready!", fg=self.c_gold)
                    card0["prog_bar"]["value"] = min(100.0, (excavations / 1500.0) * 100.0)
                    card0["clear_btn"].configure(text="🔵 Dig to 1500+ / Egg", state="normal", bg=self.c_blue, fg="white")
                    self.bind_hover(card0["clear_btn"], "Dig for Egg: Excavates up to 1,500 using available coins to find Spiky Rough Egg.")

            for index,view in dragon_stage_views(st,self.clearer.actions.catalog()).items():
                card=self.stage_cards[index]
                card['status_lbl'].configure(text=view['status'],fg=self.c_green if view['ownership_verified'] else self.c_amber)
                card['prog_lbl'].configure(text=view['detail'],fg=self.c_muted)
                card['prog_bar']['value']=view['progress']
                enabled=view['can_check'] and input_allowed(self.clearer.window)
                card['clear_btn'].configure(state='normal' if enabled else 'disabled',
                    text='Check verified milestone' if enabled else 'Needs verified prerequisites')
            if is_paused or not build_status['build_verified']:
                self.overall_eta_lbl.configure(text='ETA: measuring / prerequisites')
                self.overall_target_lbl.configure(text='')
                self.r46_eta_badge.configure(text='R46 ETA: not established')
                if not is_paused:self.worker_badge.configure(text='Setup / verification needed',fg=self.c_amber)

            # 4. Update Advisor
            route=self.clearer.actions.route.plan(st)
            _,rec=selected_route(st,load_config().get('selected_path','Automatic'))
            self.route_detail.configure(text=f"Next: {route.get('target') or route['action']}\n{route['reason']}")
            self.active_gate_sublbl.configure(text=f"Next: {route.get('target') or route['action']} | {route['reason'][:74]}")
            self.master_clear_btn.configure(text='START SELECTED\nPATH')
            self.adv_build_name.configure(text=f"Recommended: {rec['name']}")
            self.adv_build_meta.configure(text=f"Faction: {rec['faction']} | Bloodline: {rec['bloodline']}")
            self.adv_build_notes.configure(text="; ".join(build_status["missing"]) or "Build ownership verified")
            if not self.template_text.get("1.0", "end").strip():
                self.template_text.insert("1.0", rec["template"])

        except Exception as e:
            self.set_feedback(f"Telemetry error: {e}",self.c_red)

    def update_logs(self):
        if os.path.exists(LOG_FILE):
            try:
                file_size = os.path.getsize(LOG_FILE)
                if self.last_log_pos == 0 and file_size > 15000:
                    self.last_log_pos = max(0, file_size - 15000)

                with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(self.last_log_pos)
                    new_lines = f.read()
                    self.last_log_pos = f.tell()
                    if new_lines:
                        self.log_text.insert("end", new_lines)
                        line_count = int(self.log_text.index("end-1c").split(".")[0])
                        if line_count > 600:
                            self.log_text.delete("1.0", f"{line_count - 400}.0")
                        self.log_text.see("end")
            except Exception:
                pass

    def update_loop(self):
        self.update_state()
        self.update_logs()
        self.root.after(2500, self.update_loop)


def launch_monitor():
    import traceback
    try:
        root = tk.Tk()
        app = ModernDragonTrackerApp(root)
        root.mainloop()
    except Exception:
        crash_log = os.path.join(os.path.dirname(__file__), "..", "logs", "monitor_crash.log")
        with open(crash_log, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())


if __name__ == "__main__":
    launch_monitor()
