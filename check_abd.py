import math
from src.save_reader import get_current_game_state

st = get_current_game_state()
coins = st['coins']
total_gems = math.sqrt(1 + 8 * coins / 1e12) / 2
current_gems = st['gems']
reinc = st['reincarnation']

print(f"Reincarnation: {reinc}")
print(f"Current Coins: {coins:.4e}")
print(f"Total potential gems: {total_gems:.4e}")
print(f"Current gems: {current_gems:.4e}")
print(f"Net gain: {total_gems - current_gems:.4e}")
