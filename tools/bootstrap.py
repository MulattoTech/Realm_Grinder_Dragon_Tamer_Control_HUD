"""Initialize a fresh checkout; all generated game metadata remains local."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.bootstrap import initialize

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-dir',type=Path)
    parser.add_argument('--refresh-installed',action='store_true')
    args=parser.parse_args()
    print(json.dumps(initialize(game_dir=args.game_dir,refresh_installed=args.refresh_installed),indent=2))

if __name__=='__main__':main()
