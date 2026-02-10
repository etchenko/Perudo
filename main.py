from agents import RandomAgent, ConservativeAgent
from game_engine import LiarDiceEngine


def main():
    engine = LiarDiceEngine(wild_ones=True, starting_dice=5)
    engine.add_players([
        ConservativeAgent("Alice"),
        ConservativeAgent("Bob"),
        ConservativeAgent("Cara"),
    ])
    engine.play_game(verbose=True)


if __name__ == "__main__":
    main()
