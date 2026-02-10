from __future__ import annotations

import random
from typing import Sequence

from models import Action, PublicState


class Agent:
    def __init__(self, name: str):
        self.name = name

    def decide(self, state_view: PublicState, legal_actions: Sequence[Action]) -> Action:
        """
        Override to implement strategy. Receives a partial, public state view for
        the active player with fields:
          - players: PlayerPublic entries (name, dice_remaining, mine)
          - current_bid: Bid or None
          - round_number, faces, wild_ones
          - my_dice: [int]
          - round_bids: RoundBidPublic entries (player_name, quantity, face)
        Must return one of the provided legal actions.
        """
        raise NotImplementedError


class RandomAgent(Agent):
    def decide(self, state_view: PublicState, legal_actions: Sequence[Action]) -> Action:
        # Naive: prefer bids early, challenge sometimes
        bids = [a for a in legal_actions if a.kind == 'bid']
        others = [a for a in legal_actions if a.kind != 'bid']
        # Slight bias towards bidding if available
        if bids and random.random() < 0.7:
            return random.choice(bids)
        return random.choice(legal_actions)


class ConservativeAgent(Agent):
    """Challenges aggressively unless the bid is plausible given my dice."""

    def decide(self, state_view: PublicState, legal_actions: Sequence[Action]) -> Action:
        # If can challenge, decide based on simple heuristic
        challenge = next((a for a in legal_actions if a.kind == 'challenge'), None)
        bids = [a for a in legal_actions if a.kind == 'bid']
        current_bid = state_view.current_bid
        if challenge and current_bid:
            face = int(current_bid.face)
            my_dice = state_view.my_dice
            my_face_count = sum(1 for d in my_dice if d == face)
            if state_view.wild_ones and face != 1:
                my_face_count += sum(1 for d in my_dice if d == 1)
            # If my expected contribution is very low relative to quantity, challenge
            quantity = int(current_bid.quantity)
            if my_face_count <= max(0, quantity - 2):
                return challenge
        # Else bid minimally higher
        if bids:
            # choose the lowest legal bid to keep risk lower
            min_bid = min((a.bid for a in bids if a.bid), key=lambda b: (b.quantity, b.face))
            return Action(kind='bid', bid=min_bid)
        # Fallback
        return random.choice(legal_actions)
