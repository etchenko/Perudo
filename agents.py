from __future__ import annotations

import random
from typing import List, Sequence, Optional

from models import Action, Bid, GameState


class Agent:
    def __init__(self, name: str):
        self.name = name

    def decide(self, state: GameState, legal_actions: Sequence[Action]) -> Action:
        """
        Override to implement strategy. Receives a partial-observable state view 
        and must return one of the provided legal actions.
        """
        raise NotImplementedError


class RandomAgent(Agent):
    def decide(self, state: GameState, legal_actions: Sequence[Action]) -> Action:
        # Naive: prefer bids early, challenge sometimes
        bids = [a for a in legal_actions if a.kind == 'bid']
        others = [a for a in legal_actions if a.kind != 'bid']
        # Slight bias towards bidding if available
        if bids and random.random() < 0.7:
            return random.choice(bids)
        return random.choice(legal_actions)


class ConservativeAgent(Agent):
    """Challenges aggressively unless the bid is plausible given my dice."""

    def decide(self, state: GameState, legal_actions: Sequence[Action]) -> Action:
        # If can challenge, decide based on simple heuristic
        challenge = next((a for a in legal_actions if a.kind == 'challenge'), None)
        bids = [a for a in legal_actions if a.kind == 'bid']
        if challenge and state.current_bid:
            my_face_count = sum(1 for d in state.players[state.current_player_idx].dice if d == state.current_bid.face)
            if state.wild_ones and state.current_bid.face != 1:
                my_face_count += sum(1 for d in state.players[state.current_player_idx].dice if d == 1)
            # If my expected contribution is very low relative to quantity, challenge
            if my_face_count <= max(0, state.current_bid.quantity - 2):
                return challenge
        # Else bid minimally higher
        if bids:
            # choose the lowest legal bid to keep risk lower
            min_bid = min((a.bid for a in bids if a.bid), key=lambda b: (b.quantity, b.face))
            return Action(kind='bid', bid=min_bid)
        # Fallback
        return random.choice(legal_actions)
