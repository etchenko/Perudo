from game_engine import LiarDiceEngine
from agents.conservative_agent import ConservativeAgent
from agents.test_agent1 import TestAgent1
from agents.test_agent2 import TestAgent2
from simulation import Simulation


def main():
    # Uncomment to test the engine
    engine = LiarDiceEngine(wild_ones=True, starting_dice=5)
    engine.add_players([
        ConservativeAgent("Alice"),
        ConservativeAgent("Dave"),
        TestAgent1("Cara"),
        TestAgent2("Eve"),
    ])
    engine.play_game(verbose=True)


    # Uncomment to test the simulation
    #sim = Simulation(n_players_per_table = 6, n_tables = 15, n_replications = 100)
    #results = sim.start(verbose=True)
    #print(f"SIMULATION FINISHED. Results:\n {results}")
if __name__ == "__main__":
    main()
