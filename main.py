from agents import RandomAgent, ConservativeAgent
from game_engine import LiarDiceEngine


def main():
    engine = LiarDiceEngine(wild_ones=False, starting_dice=2)
    engine.add_players([
        ConservativeAgent("Alice"),
        RandomAgent("Dave"),
        ConservativeAgent("Bob"),
        ConservativeAgent("Cara"),
        RandomAgent("Eve"),
    ])
    engine.play_game(verbose=True)


if __name__ == "__main__":
    main()
