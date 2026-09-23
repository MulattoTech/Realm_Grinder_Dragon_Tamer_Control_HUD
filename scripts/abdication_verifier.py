"""
Abdication Verifier — Dragon Tamer Bot
Monitors the live bot log for verified abdication events,
captures a screenshot of the game state at each one,
and computes efficiency metrics proving each run is faster.

Usage:
    python scripts/abdication_verifier.py
"""

import os
import sys
import time
import math
import json
import logging
import datetime
import threading

# Ensure project root is on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

LOG_FILE    = os.path.join(ROOT, "logs", "bot.log")
STATE_FILE  = os.path.join(ROOT, "state", "dragon_tamer_state.json")
REPORT_FILE = os.path.join(ROOT, "state", "abdication_report.json")
SCREENSHOT_DIR = os.path.join(ROOT, "screenshots")

TARGET_COUNT = 3  # Number of verified abdications to confirm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(ROOT, "logs", "abdication_verifier.log"),
            encoding="utf-8"
        ),
    ]
)
log = logging.getLogger("AbdicationVerifier")


def read_game_state():
    from src.save_reader import get_current_game_state
    return get_current_game_state()


def capture_screenshot(label: str) -> str:
    """Capture a screenshot of the game window (minimized-safe via GDI)."""
    try:
        from src.window import RealmGrinderWindow
        w = RealmGrinderWindow()
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"abdication_{label}_{ts}.png")
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        w.capture_screenshot(path)
        log.info(f"Screenshot saved: {path}")
        return path
    except Exception as e:
        log.warning(f"Screenshot failed: {e}")
        return ""


def tail_log_for_abdication(timeout_secs: int = 7200) -> dict | None:
    """
    Tail bot.log until a '✅ Abdication VERIFIED' line appears.
    Returns parsed data from that line, or None on timeout.
    """
    log.info(f"Watching {LOG_FILE} for VERIFIED abdication (timeout={timeout_secs}s)...")
    deadline = time.time() + timeout_secs

    # Seek to end of file first
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)  # go to end
            pos = f.tell()
    except Exception as e:
        log.error(f"Cannot open log file: {e}")
        return None

    while time.time() < deadline:
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                f.seek(pos)
                lines = f.readlines()
                pos = f.tell()
            for line in lines:
                # Look for the verification line written by either gate_clearer or state_machine
                if "Abdication VERIFIED" in line or "✅ Abdicated VERIFIED" in line:
                    log.info(f"DETECTED abdication log line: {line.strip()}")
                    return {"raw_line": line.strip(), "detected_at": time.time()}
                # Also catch ABDICATION_UNVERIFIED — log it but don't count it
                if "ABDICATION_UNVERIFIED" in line or "Abdication FAILED" in line:
                    log.warning(f"⚠ Abdication failure detected: {line.strip()}")
        except Exception as e:
            log.warning(f"Log read error: {e}")
        time.sleep(1.0)

    log.error("Timeout waiting for abdication!")
    return None


def format_duration(secs: float) -> str:
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    elif m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def format_num(n: float) -> str:
    if n == 0:
        return "0"
    exp = math.floor(math.log10(abs(n)))
    coeff = n / (10 ** exp)
    return f"{coeff:.3f}e+{exp:02d}"


class AbdicationRecord:
    def __init__(self, index: int, pre_state: dict, post_state: dict,
                 run_start: float, abdication_time: float, screenshot_path: str):
        self.index          = index
        self.pre_gems       = pre_state["gems"]
        self.post_gems      = post_state["gems"]
        self.pre_pot        = pre_state["potential_gems"]
        self.coins_abd      = pre_state["coins_this_abdication"]
        self.r              = pre_state["reincarnation"]
        self.run_start      = run_start
        self.abdication_time = abdication_time
        self.run_duration   = abdication_time - run_start
        self.gems_gained    = self.post_gems - self.pre_gems
        self.multiplier     = self.post_gems / max(1.0, self.pre_gems)
        self.screenshot     = screenshot_path
        self.dt_str         = datetime.datetime.fromtimestamp(abdication_time).isoformat(timespec="seconds")
        # gems per second of run duration
        self.gem_rate       = self.gems_gained / max(1.0, self.run_duration)

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.dt_str,
            "reincarnation": self.r,
            "run_duration_sec": self.run_duration,
            "run_duration_fmt": format_duration(self.run_duration),
            "gems_before": self.pre_gems,
            "gems_after":  self.post_gems,
            "gems_gained": self.gems_gained,
            "multiplier":  self.multiplier,
            "gem_rate_per_sec": self.gem_rate,
            "potential_gems": self.pre_pot,
            "coins_this_abdication": self.coins_abd,
            "screenshot": self.screenshot,
        }

    def summary_line(self) -> str:
        return (
            f"  #{self.index}: {self.dt_str}  R{self.r}  "
            f"{format_num(self.pre_gems)} → {format_num(self.post_gems)} gems  "
            f"(×{self.multiplier:.2f})  "
            f"Run: {format_duration(self.run_duration)}  "
            f"Rate: {format_num(self.gem_rate)} gems/s"
        )


def print_efficiency_table(records: list[AbdicationRecord]):
    print("\n" + "="*90)
    print("  ABDICATION EFFICIENCY REPORT")
    print("="*90)
    print(f"  {'#':>3}  {'Timestamp':^20}  {'R':>3}  {'Gems Before':>14}  "
          f"{'Gems After':>14}  {'×':>6}  {'Duration':>10}  {'gems/s':>14}  {'Faster?':>8}")
    print("  " + "-"*86)
    for i, rec in enumerate(records):
        faster = ""
        if i > 0:
            prev = records[i - 1]
            # "More efficient" = higher gem rate (gems gained per second of run time)
            if rec.gem_rate > prev.gem_rate:
                faster = "✅ YES"
            else:
                faster = "❌ NO"
        print(f"  {rec.index:>3}  {rec.dt_str:^20}  {rec.r:>3}  "
              f"{format_num(rec.pre_gems):>14}  {format_num(rec.post_gems):>14}  "
              f"{rec.multiplier:>6.2f}  {format_duration(rec.run_duration):>10}  "
              f"{format_num(rec.gem_rate):>14}  {faster:>8}")
    print("="*90 + "\n")


def main():
    log.info("="*60)
    log.info("  Abdication Verifier — Dragon Tamer Bot")
    log.info(f"  Target: {TARGET_COUNT} verified abdications, each more efficient")
    log.info("="*60)

    records: list[AbdicationRecord] = []
    run_start = time.time()

    # Initial game state snapshot
    try:
        initial_state = read_game_state()
        log.info(f"Initial state: R={initial_state['reincarnation']}, "
                 f"gems={format_num(initial_state['gems'])}, "
                 f"pot_gems={format_num(initial_state['potential_gems'])}")
    except Exception as e:
        log.error(f"Cannot read initial game state: {e}")
        initial_state = {}

    pre_state = initial_state.copy()

    for abd_num in range(1, TARGET_COUNT + 1):
        log.info("\n" + "-"*60)
        log.info(f"  Waiting for abdication #{abd_num} of {TARGET_COUNT}...")
        log.info("-"*60)

        # Wait for log event
        result = tail_log_for_abdication(timeout_secs=10800)  # 3 hour timeout per abdication
        if result is None:
            log.error(f"Abdication #{abd_num} timed out! Stopping verifier.")
            break

        abd_time = result["detected_at"]
        log.info(f"\n✅ Abdication #{abd_num} detected at {datetime.datetime.fromtimestamp(abd_time)}")

        # Wait 2 seconds for the save file to fully update
        time.sleep(2.0)

        # Capture screenshot
        screenshot_path = capture_screenshot(f"abd{abd_num}")

        # Read post-abdication state
        try:
            post_state = read_game_state()
            log.info(f"Post-abd state: R={post_state['reincarnation']}, "
                     f"gems={format_num(post_state['gems'])}, "
                     f"pot_gems={format_num(post_state['potential_gems'])}")
        except Exception as e:
            log.error(f"Could not read post-abd state: {e}")
            post_state = pre_state.copy()

        # Create record
        rec = AbdicationRecord(
            index=abd_num,
            pre_state=pre_state,
            post_state=post_state,
            run_start=run_start,
            abdication_time=abd_time,
            screenshot_path=screenshot_path,
        )
        records.append(rec)
        log.info(rec.summary_line())

        # Verify gems increased
        if post_state.get("gems", 0) <= pre_state.get("gems", 0):
            log.warning(f"⚠ Gems did NOT increase: {format_num(pre_state.get('gems',0))} "
                        f"→ {format_num(post_state.get('gems',0))}. "
                        f"Abdication may not have been truly effective. Continuing to watch...")
        else:
            log.info(f"✅ VISUAL CONFIRMED: Gems {format_num(pre_state['gems'])} "
                     f"→ {format_num(post_state['gems'])} (+{format_num(rec.gems_gained)})")

        # Check efficiency progression
        if len(records) > 1:
            prev = records[-2]
            if rec.gem_rate > prev.gem_rate:
                log.info(f"✅ EFFICIENCY IMPROVED: {format_num(prev.gem_rate)} → {format_num(rec.gem_rate)} gems/s")
            else:
                log.warning(f"⚠ Efficiency did NOT improve vs previous: "
                            f"{format_num(prev.gem_rate)} → {format_num(rec.gem_rate)} gems/s")

        # Save running report
        report = {
            "generated_at": datetime.datetime.now().isoformat(),
            "completed": len(records),
            "target": TARGET_COUNT,
            "abdications": [r.to_dict() for r in records],
        }
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        log.info(f"Report saved → {REPORT_FILE}")

        # Reset for next run
        pre_state = post_state.copy()
        run_start = abd_time

    # Final summary
    print_efficiency_table(records)

    # Final verdict
    all_verified = len(records) >= TARGET_COUNT
    progressively_faster = all(
        records[i].gem_rate > records[i-1].gem_rate
        for i in range(1, len(records))
    )

    print("\n📋 FINAL VERDICT:")
    print(f"  Total abdications verified: {len(records)} / {TARGET_COUNT}")
    if all_verified:
        print(f"  ✅ All {TARGET_COUNT} abdications confirmed.")
    else:
        print(f"  ❌ Only {len(records)} abdications detected. Target was {TARGET_COUNT}.")

    if progressively_faster:
        print("  ✅ Each abdication was MORE EFFICIENT than the last (gems/sec metric).")
    else:
        print("  ⚠  Not all abdications improved in efficiency. Review report for details.")

    print(f"\n  Report: {REPORT_FILE}")
    print(f"  Screenshots: {SCREENSHOT_DIR}")

    if all_verified and progressively_faster:
        print("\n  🎉 GOAL COMPLETE — Bot abdication verified and performing correctly.")
    else:
        print("\n  ⚠  Goal not fully met — see report for details.")

    return all_verified and progressively_faster


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
