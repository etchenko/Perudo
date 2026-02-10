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
class PublicState:
    players: List[PlayerPublic]
    current_bid: Optional[Bid]
    round_number: int
    faces: int
    wild_ones: bool
    my_dice: List[int]
    round_bids: List[RoundBidPublic]
    game_history: List[RoundBidPublic]
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
    game_history: List[RoundBid]

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
        game_history_public = [
            RoundBidPublic(player_name=rb.player_name, quantity=rb.bid.quantity, face=rb.bid.face, round_number=rb.round_number)
            for rb in self.game_history
        ]
        return PublicState(
            players=players_public,
            current_bid=self.current_bid,
            round_number=self.round_number,
            faces=self.faces,
            wild_ones=self.wild_ones,
            my_dice=list(self.players[player_idx].dice),
            round_bids=round_bids_public,
            game_history=game_history_public,
            permutation_number=0,  # Will be set by engine in the future
        )


@dataclass
class RoundResult:
    winner_idx: int
    loser_idx: int
    revealed_counts: Dict[int, int]  # face -> count
    resolved_on: str  # 'challenge' | 'exact'
    bid: Optional[Bid]
