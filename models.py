from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass(frozen=True)
class Bid:
    quantity: int
    face: int  # 1..faces

    def __str__(self) -> str:
        return f"{self.quantity} x {self.face}s"


@dataclass(frozen=True)
class Action:
    kind: str  # 'bid' | 'challenge' | 'exact'
    bid: Optional[Bid] = None

    def __str__(self) -> str:
        if self.kind == 'bid' and self.bid:
            return f"Bid({self.bid})"
        return self.kind.capitalize()


@dataclass
class PlayerState:
    name: str
    dice_remaining: int
    dice: List[int]
    # Keep a stable reference to the controlling agent to avoid index mismatch
    agent: object


@dataclass(frozen=True)
class RoundBid:
    player_idx: int
    player_name: str
    bid: Bid
    round_number: int


@dataclass(frozen=True)
class RoundResolution:
    """Records how a round ended and what was revealed"""
    round_number: int
    bids: List[RoundBid]  # All bids made during this round
    final_bid: Bid
    resolution_type: str  # 'challenge' or 'exact'
    resolver_name: str  # Who called challenge/exact
    winner_name: str
    loser_name: str
    actual_count: int  # Actual count of the bid face
    revealed_dice: Dict[str, List[int]]  # player_name -> their dice


@dataclass(frozen=True)
class PlayerPublic:
    name: str
    dice_remaining: int
    mine: bool


@dataclass(frozen=True)
class RoundBidPublic:
    player_name: str
    quantity: int
    face: int
    round_number: int


@dataclass(frozen=True)
class RoundResolutionPublic:
    """Public view of how a round ended"""
    round_number: int
    bids: List[RoundBidPublic]  # All bids made during this round
    final_bid_quantity: int
    final_bid_face: int
    resolution_type: str  # 'challenge' or 'exact'
    resolver_name: str
    winner_name: str
    loser_name: str
    actual_count: int
    revealed_dice: Dict[str, List[int]]


@dataclass(frozen=True)
class PublicState:
    players: List[PlayerPublic]
    current_bid: Optional[Bid]
    round_number: int
    faces: int
    wild_ones: bool
    my_dice: List[int]
    round_bids: List[RoundBidPublic]
    round_resolutions: List[RoundResolutionPublic]  # How each round ended
    permutation_number: int


@dataclass
class GameState:
    players: List[PlayerState]
    current_player_idx: int
    current_bid: Optional[Bid]
    round_number: int
    faces: int
    wild_ones: bool
    round_bids: List[RoundBid]
    round_resolutions: List[RoundResolution]  # Complete history of round endings

    def total_dice_in_play(self) -> int:
        return sum(p.dice_remaining for p in self.players)

    def visible_summary_for(self, player_idx: int) -> PublicState:
        # Expose only what agents should see in a typed dataclass
        players_public = [
            PlayerPublic(name=p.name, dice_remaining=p.dice_remaining, mine=(i == player_idx))
            for i, p in enumerate(self.players)
        ]
        round_bids_public = [
            RoundBidPublic(player_name=rb.player_name, quantity=rb.bid.quantity, face=rb.bid.face, round_number=rb.round_number)
            for rb in self.round_bids
        ]
        round_resolutions_public = [
            RoundResolutionPublic(
                round_number=rr.round_number,
                bids=[
                    RoundBidPublic(player_name=rb.player_name, quantity=rb.bid.quantity, face=rb.bid.face, round_number=rb.round_number)
                    for rb in rr.bids
                ],
                final_bid_quantity=rr.final_bid.quantity,
                final_bid_face=rr.final_bid.face,
                resolution_type=rr.resolution_type,
                resolver_name=rr.resolver_name,
                winner_name=rr.winner_name,
                loser_name=rr.loser_name,
                actual_count=rr.actual_count,
                revealed_dice=rr.revealed_dice,
            )
            for rr in self.round_resolutions
        ]
        return PublicState(
            players=players_public,
            current_bid=self.current_bid,
            round_number=self.round_number,
            faces=self.faces,
            wild_ones=self.wild_ones,
            my_dice=list(self.players[player_idx].dice),
            round_bids=round_bids_public,
            round_resolutions=round_resolutions_public,
            permutation_number=0,  # Will be set by engine in the future
        )


@dataclass
class RoundResult:
    winner_idx: int
    loser_idx: int
    revealed_counts: Dict[int, int]  # face -> count
    resolved_on: str  # 'challenge' | 'exact'
    bid: Optional[Bid]


class Agent:
    def __init__(self, name: str="Default Name"):
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
    
    def game_finished(self, winner_name: str, round_resolutions: List[RoundResolution]) -> None:
        """
        Called at the end of each game. Override to update internal state, weights, or learn from outcomes.
        
        Args:
            winner_name: Name of the winning player
            round_resolutions: Complete list of how each round ended, including challenges/exacts and revealed dice
        """
        pass  # Default implementation does nothing