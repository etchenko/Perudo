from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple


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


@dataclass
class GameState:
    players: List[PlayerState]
    current_player_idx: int
    current_bid: Optional[Bid]
    round_number: int
    faces: int
    wild_ones: bool

    def total_dice_in_play(self) -> int:
        return sum(p.dice_remaining for p in self.players)

    def visible_summary_for(self, player_idx: int) -> Dict[str, object]:
        # Expose only what agents should see
        return {
            'players': [
                {
                    'name': p.name,
                    'dice_remaining': p.dice_remaining,
                    'mine': i == player_idx,
                }
                for i, p in enumerate(self.players)
            ],
            'current_player_idx': self.current_player_idx,
            'current_bid': None if self.current_bid is None else {
                'quantity': self.current_bid.quantity,
                'face': self.current_bid.face,
            },
            'round_number': self.round_number,
            'faces': self.faces,
            'wild_ones': self.wild_ones,
            'my_dice': list(self.players[player_idx].dice),
        }


@dataclass
class RoundResult:
    winner_idx: int
    loser_idx: int
    revealed_counts: Dict[int, int]  # face -> count
    resolved_on: str  # 'challenge' | 'exact'
    bid: Optional[Bid]
