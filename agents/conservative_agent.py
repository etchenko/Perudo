from __future__ import annotations

from models import Action, Agent, Bid, PublicState


class ConservativeAgent(Agent):
    """Challenges aggressively unless the bid is plausible given my dice."""
    def __init__(self, name:str="conservative"):
        super()
        self.name = name

    def decide(self, state_view: PublicState) -> Action:
        # If can challenge, decide based on simple heuristic
        current_bid = state_view.current_bid
        total_dice = sum(p.dice_remaining for p in state_view.players if p.name != self.name)
        if current_bid:
            face = int(current_bid.face)
            my_dice = state_view.my_dice
            my_face_count = sum(1 for d in my_dice if d == face)
            if state_view.wild_ones and face != 1:
                my_face_count += sum(1 for d in my_dice if d == 1)

            if current_bid.quantity >= my_face_count + (total_dice /(state_view.faces if not state_view.wild_ones or face == 1 else state_view.faces - 1)):
                # If the bid is not plausible given my dice, challenge
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
