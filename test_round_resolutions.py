"""Quick test to verify round resolutions with revealed dice work correctly"""

from game_engine import LiarDiceEngine
from agents.random_agent import RandomAgent
from models import Agent, RoundResolution

class VerifyingAgent(Agent):
    """Agent that verifies it receives round resolutions with revealed dice"""
    def __init__(self, name):
        super().__init__(name)
        self.received_resolutions = False
    
    def decide(self, state_view):
        from models import Action, Bid
        # Just bid randomly
        if state_view.current_bid is None:
            return Action(kind='bid', bid=Bid(1, 2))
        else:
            return Action(kind='challenge')
    
    def game_finished(self, winner_name, round_resolutions):
        """Check that we receive valid round resolutions"""
        print(f"\n{self.name} received game_finished callback!")
        print(f"Winner: {winner_name}")
        print(f"Number of rounds: {len(round_resolutions)}")
        
        for i, resolution in enumerate(round_resolutions):
            print(f"\nRound {resolution.round_number}:")
            print(f"  Bids made this round:")
            for bid_record in resolution.bids:
                print(f"    {bid_record.player_name}: {bid_record.bid.quantity}x{bid_record.bid.face}")
            print(f"  Final bid: {resolution.final_bid.quantity}x{resolution.final_bid.face}")
            print(f"  Resolution: {resolution.resolution_type}")
            print(f"  Resolver: {resolution.resolver_name}")
            print(f"  Winner: {resolution.winner_name}, Loser: {resolution.loser_name}")
            print(f"  Actual count: {resolution.actual_count}")
            print(f"  Revealed dice:")
            for player_name, dice in resolution.revealed_dice.items():
                print(f"    {player_name}: {dice}")
        
        self.received_resolutions = True

# Run a quick game
engine = LiarDiceEngine(starting_dice=3, wild_ones=True)
agent1 = VerifyingAgent("Alice")
agent2 = RandomAgent("Bob")

engine.add_players([agent1, agent2])
winner = engine.play_game(verbose=False)

print(f"\n{'='*60}")
print(f"Game complete! Winner: {winner}")
print(f"Agent received resolutions: {agent1.received_resolutions}")
