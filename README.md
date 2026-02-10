# Liar's Dice (Perudo) Engine

This engine manages the game state for Liar's Dice (aka Perudo), exposes legal actions to agents, and runs rounds until a single player remains.

## Features
- Configurable faces (default 6), starting dice (default 5), and Wild Ones rule.
- Strictly increasing bids by quantity then face.
- Challenge (Dudo) resolution with dice reveal and loser loses one die.
- Optional Exact call (disabled by default). In this simple variant, correct exact grants the caller +1 die (capped to starting dice); incorrect exact loses one die.
- Agent interface with sample `RandomAgent` and `ConservativeAgent`.

## Files
- `models.py` — core dataclasses for `Bid`, `Action`, `PlayerState`, `GameState`, `RoundResult`.
- `agents.py` — agent interface and sample agents.
- `game_engine.py` — engine implementation and a runnable `demo_game()`.

## Quick Start
Run a demo game:

```bash
python3 game_engine.py
```

You can customize players by creating your own agent that subclasses `Agent` and implements `decide(state, legal_actions)`.

## Agent API
- `decide(state: GameState, legal_actions: Sequence[Action]) -> Action`
  - Must return one of the provided legal actions.
  - `state.visible_summary_for(player_idx)` exposes a safe subset; the engine passes the full `GameState` to keep things simple here, but agents should only rely on their own dice and public info.

## Notes
- Wild Ones: when counting a face (e.g., 4s), ones contribute to the total unless the face itself is 1.
- Bids must strictly increase: higher quantity or same quantity with higher face.
- House rules vary; adjust logic as desired.
