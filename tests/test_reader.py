from src.save_reader import get_current_game_state

def test_reader():
    st = get_current_game_state()
    print("Reincarnation:", st["reincarnation"])
    print("Excavations:", st["excavations"])
    print("Gems:", f"{st['gems']:.4e}")
    print("Has Spiky Rough Egg:", st["has_egg"])
    print("Hellfire active time:", st["hellfire_time"])

if __name__ == "__main__":
    test_reader()
