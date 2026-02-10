from __future__ import annotations

import random
from typing import List

from models import Action, PublicState, Bid


class Agent:
    def __init__(self, name: str):
        self.name = name

    def decide(self, state_view: PublicState) -> Action:
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
    def decide(self, state_view: PublicState) -> Action:
        # Naive: prefer bids early, challenge sometimes
        def possible_bids() -> List[Bid]:
            total = sum(p.dice_remaining for p in state_view.players)
            cur = state_view.current_bid
            faces = state_view.faces
            out: List[Bid] = []
            for q in range(1, total + 1):
                for f in range(1, faces + 1):
                    b = Bid(q, f)
                    if cur is None or (b.quantity > cur.quantity) or (b.quantity == cur.quantity and b.face > cur.face):
                        out.append(b)
            return out

        bids = possible_bids()
        if bids and random.random() < 0.7:
            return Action(kind='bid', bid=random.choice(bids))
        # If there is a current bid, sometimes challenge/exact
        if state_view.current_bid is not None:
            if state_view.round_number % 2 == 0 and random.random() < 0.5 and state_view.wild_ones:
                return Action(kind='exact')
            return Action(kind='challenge')
        # Otherwise, must bid
        return Action(kind='bid', bid=bids[0] if bids else Bid(1, 1))


class ConservativeAgent(Agent):
    """Challenges aggressively unless the bid is plausible given my dice."""

    def decide(self, state_view: PublicState) -> Action:
        # If can challenge, decide based on simple heuristic
        current_bid = state_view.current_bid
        if current_bid:
            face = int(current_bid.face)
            my_dice = state_view.my_dice
            my_face_count = sum(1 for d in my_dice if d == face)
            if state_view.wild_ones and face != 1:
                my_face_count += sum(1 for d in my_dice if d == 1)
            # If my expected contribution is very low relative to quantity, challenge
            quantity = int(current_bid.quantity)
            if my_face_count <= max(0, quantity - 2):
                return Action(kind='challenge')
        
        # When bidding, prefer faces we actually have
        total = sum(p.dice_remaining for p in state_view.players)
        faces = state_view.faces
        my_dice = state_view.my_dice
        
        # Count our dice for each face (including wild ones)
        face_counts = {}
        for f in range(1, faces + 1):
            count = sum(1 for d in my_dice if d == f)
            if state_view.wild_ones and f != 1:
                count += sum(1 for d in my_dice if d == 1)
            face_counts[f] = count
        
        if current_bid is None:
            # Initial bid: choose the face we have the most of at quantity 1
            best_face = max(range(1, faces + 1), key=lambda f: face_counts[f])
            return Action(kind='bid', bid=Bid(1, best_face))
        
        # Find minimal strictly higher bid, preferring faces we have
        # Need to respect wild ones rules for bidding on/from ones
        candidates = []
        
        if state_view.wild_ones:
            import math
            # Special rules for wild ones games
            if current_bid.face == 1:
                # Current bid is on ones
                # Can bid higher ones, or must double+1 for other faces
                for q in range(current_bid.quantity + 1, total + 1):
                    candidates.append((Bid(q, 1), face_counts[1]))
                for f in range(2, faces + 1):
                    min_q = current_bid.quantity * 2 + 1
                    for q in range(min_q, total + 1):
                        candidates.append((Bid(q, f), face_counts[f]))
            else:
                # Current bid is not on ones
                # Can bid higher on same or higher face, or switch to ones with halved quantity
                for q in range(current_bid.quantity, total + 1):
                    for f in range(1, faces + 1):
                        b = Bid(q, f)
                        if f == 1:
                            # Moving to ones: need at least ceil(current_quantity / 2)
                            min_ones = math.ceil(current_bid.quantity / 2.0)
                            if q >= min_ones:
                                candidates.append((b, face_counts[f]))
                        elif (b.quantity > current_bid.quantity) or (b.quantity == current_bid.quantity and b.face > current_bid.face):
                            candidates.append((b, face_counts[f]))
        else:
            # Standard rules
            for q in range(current_bid.quantity, total + 1):
                for f in range(1, faces + 1):
                    b = Bid(q, f)
                    # Check if strictly higher
                    if (b.quantity > current_bid.quantity) or (b.quantity == current_bid.quantity and b.face > current_bid.face):
                        candidates.append((b, face_counts[f]))
        
        if not candidates:
            # No valid higher bid, challenge
            return Action(kind='challenge')
        
        # Sort by: strictly increasing (q, f), then by count descending (prefer faces we have)
        candidates.sort(key=lambda x: (x[0].quantity, x[0].face, -x[1]))
        return Action(kind='bid', bid=candidates[0][0])
