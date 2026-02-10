# Perudo (Liar's Dice) Game Engine

A Python implementation of Perudo (Liar's Dice) with support for custom agents.

## Game Rules

Perudo is a dice game of deception and probability. Players bid on the total number of dice showing a particular face across all players' hands.

### Setup
- Each player starts with 5 dice (configurable)
- Players roll their dice and keep them hidden from others
- Standard 6-sided dice (1-6) (configurable)

### Wild Ones Rule
When playing with wild ones (default):
- **Ones are wild**: When counting any face value (2-6), ones also count toward that total
- **Betting on ones**: When the bid is specifically on ones, only ones count (they are not wild for themselves)
- **Special bidding rules for ones**:
  - **Bidding TO ones**: You can halve the current quantity (rounded up)
    - Example: Current bid is 6×4 → You can bid 3×1 (ceil(6/2)=3)
  - **Bidding FROM ones**: You must at least double the quantity plus one
    - Example: Current bid is 3×1 → You must bid at least 7×2 (3×2+1=7)
  - **Bidding ones to ones**: Standard rule applies (quantity must be strictly higher)

### Gameplay
Players take turns either:
1. **Making a bid**: Claim a quantity and face value (e.g., "five 4s")
   - Must be strictly higher than the previous bid:
     - Higher quantity with any face, OR
     - Same quantity with a higher face value
   - With wild ones enabled, special rules apply (see above)

2. **Calling "Challenge" (Dudo)**: Claim the previous bid is too high
   - All dice are revealed and counted
   - If the bid quantity is met or exceeded → Bidder wins, challenger loses a die
   - If the bid quantity is not met → Challenger wins, bidder loses a die

3. **Calling "Exact" (Calza)**: Claim the previous bid is exactly correct
   - All dice are revealed and counted
   - If exactly correct → Caller gains one die (max 5), previous bidder loses a die
   - If incorrect → Caller loses one die, previous bidder wins

### Winning
- When a player loses their last die, they are eliminated
- Last player remaining wins the game

### Rules Not Implemented
- **Palifico**: Not used in this implementation

## For Agent Developers

### Creating a Custom Agent

To create your own agent, inherit from the `Agent` base class and implement the `decide` method:

```python
from agents import Agent
from models import Action, PublicState, Bid

class MyAgent(Agent):
    def decide(self, state_view: PublicState) -> Action:
        # Your logic here
        return Action(kind='bid', bid=Bid(1, 2))
```

### Game State Information

Your agent's `decide` method receives a `PublicState` object with the following information:

#### PublicState Fields

```python
state_view.players          # List[PlayerPublic] - Info about all players
state_view.current_bid      # Optional[Bid] - The current bid (None if first bid)
state_view.round_number     # int - Current round number
state_view.faces            # int - Number of faces on dice (usually 6)
state_view.wild_ones        # bool - Whether ones are wild
state_view.my_dice          # List[int] - YOUR dice (only you can see these)
state_view.round_bids       # List[RoundBidPublic] - Bids made this round
state_view.round_resolutions # List[RoundResolutionPublic] - How each round ended
```

#### PlayerPublic Fields

Each entry in `state_view.players` contains:
```python
player.name               # str - Player name
player.dice_remaining     # int - How many dice they have left
player.mine               # bool - True if this is your player
```

#### RoundBidPublic Fields

Each bid in `round_bids` contains:
```python
bid.player_name          # str - Who made the bid
bid.quantity             # int - Number of dice bid
bid.face                 # int - Face value bid (1-6)
bid.round_number         # int - Which round this bid was made
```

#### RoundResolutionPublic Fields

Each round resolution in `round_resolutions` contains:
```python
resolution.round_number         # int - Which round this was
resolution.bids                 # List[RoundBidPublic] - All bids made this round
resolution.final_bid_quantity   # int - Quantity of the final bid
resolution.final_bid_face       # int - Face of the final bid
resolution.resolution_type      # str - 'challenge' or 'exact'
resolution.resolver_name        # str - Who called challenge/exact
resolution.winner_name          # str - Who won the round
resolution.loser_name           # str - Who lost the round
resolution.actual_count         # int - Actual count of the bid face
resolution.revealed_dice        # Dict[str, List[int]] - Everyone's dice that round
```

#### Making Decisions

Your agent must return an `Action` object:

```python
# Bidding
Action(kind='bid', bid=Bid(quantity=3, face=4))  # Bid "three 4s"

# Challenge the current bid
Action(kind='challenge')

# Call exact on the current bid (if enabled)
Action(kind='exact')
```

#### Learning from Game Outcomes

Your agent can optionally implement the `game_finished` method to learn from completed games:

```python
def game_finished(self, winner_name: str, round_resolutions: List[RoundResolution]) -> None:
    # Called after each game ends
    # winner_name: Name of the winning player
    # round_resolutions: Complete history of how each round ended
    
    # Use this to update weights, adjust strategies, etc.
    if winner_name == self.name:
        # I won! Reinforce successful strategies
        pass
    else:
        # I lost. Analyze what went wrong
        for resolution in round_resolutions:
            # Access revealed dice from each round
            my_dice = resolution.revealed_dice[self.name]
            # Analyze if I should have challenged/called exact
            pass
```

This method is called automatically by the engine after every game completes, allowing your agent to:
- Update internal weights or parameters
- Analyze betting patterns and revealed dice from each round
- Implement reinforcement learning algorithms
- Track performance metrics over multiple games
- Review what everyone's dice were when challenges/exacts were called

The `round_resolutions` contains complete information about how each round ended, including the challenge/exact type, winner/loser, actual dice counts, and everyone's revealed dice for that round.

**Note** This also has a default time limit of twice the regular time limit (2 seconds)

### Important Notes

- **You only see your own dice** (`state_view.my_dice`)
- Other players' dice remain hidden until a challenge/exact call
- **The engine validates your actions** - if you return an illegal bid, it will force a challenge or minimal legal bid
- Use `state_view.round_resolutions` to see revealed dice from completed rounds
- With `wild_ones=True`, remember to account for ones when calculating probabilities

### Example Agents

Several example agents are included in the agents folders:

- **RandomAgent**: Makes random legal moves
- **ConservativeAgent**: Bids conservatively on faces it has, challenges aggressively
- **TestAgent1/2/3/4**: Various test agents for development

## Simulation System

The simulation framework allows you to test agent performance across multiple games with different player combinations.

### How Simulations Work

The `Simulation` class (in `simulation.py`) orchestrates large-scale testing:

1. **Agent Discovery**: Automatically discovers all `Agent` subclasses in the `agents/` package
2. **Table Generation**: Creates random combinations of agents to form game tables
3. **Replication**: Runs multiple games for each table combination to get statistically meaningful results
4. **Score Tracking**: Maintains both local (per-table) and global (across all tables) win counts

### Running Simulations

```python
from simulation import Simulation

# Create simulation with:
# - 6 players per table
# - 10 different table combinations
# - 100 game replications per table
sim = Simulation(
    n_players_per_table=6,
    n_tables=10,
    n_replications=100
)

# Run the simulation
global_scores = sim.start(verbose=True)

# Results: total wins across all tables for each agent
print(global_scores)
```

### Simulation Parameters

- **`n_players_per_table`**: Number of players per game (default: 6)
  - Each game table has this many agents
  - Agents are randomly sampled from all available agents

- **`n_tables`**: Number of different table combinations (default: 10)
  - Creates diverse matchups by randomly combining agents
  - Each table is a different permutation of agents

- **`n_replications`**: Games played per table (default: 100)
  - Higher values give more statistically significant results
  - Each replication uses the same agents but fresh dice rolls

### Agent Time Limits

The engine enforces a time limit on agent decisions (default: 1 second):

```python
engine = LiarDiceEngine(
    time_limit_seconds=1  # Agent has 1 second to decide
)
```

If an agent exceeds the time limit:
- A `TimeoutException` is raised
- The agent's decision is treated as invalid
- The engine forces a fallback action (challenge or minimal bid)

This ensures fair play and prevents agents from gaining advantages through excessive computation.

### Creating New Agents for Simulation

To add your agent to simulations:

1. Create a new file in the `agents/` directory (e.g., `agents/my_agent.py`)
2. Import the base `Agent` class from `models`
3. Implement your agent with a **no-argument constructor**:

```python
# agents/my_agent.py
from models import Agent, Action, PublicState, Bid

class MyAgent(Agent):
    def __init__(self):
        super().__init__("MyAgent")  # Give it a unique name
    
    def decide(self, state_view: PublicState) -> Action:
        # Your decision logic here
        return Action(kind='bid', bid=Bid(1, 2))
```

The simulation system will automatically discover and include your agent!

### Simulation Output

The simulation tracks:

- **Local Scores**: Wins at each individual table (shown with `verbose=True`)
- **Global Scores**: Total wins across all tables for each agent

Example output:
```
Replications for table 0 / 10: 100%|████████| 100/100
Stating replications for table with following table:
 ['RandomAgent', 'ConservativeAgent', 'ProbabilisticAgent', ...]

100 replications have been finished. Scores at this table:
{'RandomAgent': 12, 'ConservativeAgent': 23, 'ProbabilisticAgent': 45, ...}

...

Global Scores:
{'ProbabilisticAgent': 456, 'ConservativeAgent': 287, 'RandomAgent': 157}
```

### Statistical Analysis

With `n_tables=10` and `n_replications=100`:
- Total games: 1,000 per agent (on average)
- Different opponents: 10 unique table combinations
- Confidence: Results become more reliable with higher replication counts

This setup tests agents against various opponent combinations, preventing overfitting to specific matchups.

## Running the Game

```python
from game_engine import LiarDiceEngine
from agents.conservative_agent import ConservativeAgent
from prob_agent import ProbabilisticAgent

# Create engine
engine = LiarDiceEngine(
    wild_ones=True,        # Enable wild ones
    starting_dice=5,       # Dice per player
    faces=6,              # 6-sided dice
    exact_call_enabled=True  # Allow exact calls
)

# Add players
engine.add_players([
    ProbabilisticAgent("Alice"),
    ConservativeAgent("Bob"),
    ConservativeAgent("Carol"),
])

# Play the game
winner = engine.play_game(verbose=True)
print(f"Winner: {winner}")
```

## Running Tests

```bash
python -m unittest tests.test_engine.LiarDiceTests -v
```

## Project Structure

```
.
├── models.py              # Data classes for game state
├── agents/               # Agent implementations directory
│   ├── random_agent.py   # Random decision agent
│   ├── conservative_agent.py  # Conservative strategy agent
│   ├── test_agent1.py    # Test agent variations
│   └── ...
├── prob_agent.py         # Probabilistic agents
├── game_engine.py        # Core game engine and rules
├── simulation.py         # Simulation framework
├── main.py              # Demo game
├── tests/
│   └── test_engine.py   # Unit tests
└── README.md            # This file
```

## License

See LICENSE file for details.
