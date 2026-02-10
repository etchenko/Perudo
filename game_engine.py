from __future__ import annotations

import random
from typing import List, Optional, Sequence

from models import Bid, Action, PlayerState, GameState, RoundResult
from agents import Agent


class LiarDiceEngine:
	def __init__(
		self,
		faces: int = 6,
		starting_dice: int = 6,
		wild_ones: bool = False,
		exact_call_enabled: bool = True,
		rng: Optional[random.Random] = None,
	) -> None:
		self.faces = faces
		self.starting_dice = starting_dice
		self.wild_ones = wild_ones
		self.exact_call_enabled = exact_call_enabled
		self.rng = rng or random.Random()

		self.agents: List[Agent] = []
		self.state: Optional[GameState] = None

	def add_players(self, agents: Sequence[Agent]) -> None:
		# Keep original list for reference, but engine will use PlayerState.agent
		self.agents = list(agents)

	def _roll_dice_for(self, dice_count: int) -> List[int]:
		return [self.rng.randint(1, self.faces) for _ in range(dice_count)]

	def start_new_game(self) -> None:
		players = [PlayerState(a.name, self.starting_dice, [], agent=a) for a in self.agents]
		self.state = GameState(
			players=players,
			current_player_idx=0,
			current_bid=None,
			round_number=0,
			faces=self.faces,
			wild_ones=self.wild_ones,
		)

	def _begin_round(self) -> None:
		assert self.state is not None
		self.state.round_number += 1
		self.state.current_bid = None
		# Roll dice
		for p in self.state.players:
			p.dice = self._roll_dice_for(p.dice_remaining)

	def _next_player_idx(self, idx: int) -> int:
		assert self.state is not None
		n = len(self.state.players)
		return (idx + 1) % n

	def _alive_players(self) -> List[int]:
		assert self.state is not None
		return [i for i, p in enumerate(self.state.players) if p.dice_remaining > 0]

	def _remove_eliminated(self) -> None:
		assert self.state is not None
		self.state.players = [p for p in self.state.players if p.dice_remaining > 0]
		# Clamp current_player_idx to alive players
		if self.state.current_player_idx >= len(self.state.players):
			self.state.current_player_idx = 0

	def legal_actions(self) -> List[Action]:
		assert self.state is not None
		actions: List[Action] = []
		total = self.state.total_dice_in_play()

		# Generate all strictly higher bids
		def is_higher(b: Bid) -> bool:
			cur = self.state.current_bid
			if cur is None:
				return True
			return (b.quantity > cur.quantity) or (b.quantity == cur.quantity and b.face > cur.face)

		for q in range(1, total + 1):
			for f in range(1, self.faces + 1):
				b = Bid(q, f)
				if is_higher(b):
					actions.append(Action(kind='bid', bid=b))

		# Challenge available only if there is a current bid
		if self.state.current_bid is not None:
			actions.append(Action(kind='challenge'))
			if self.exact_call_enabled:
				actions.append(Action(kind='exact'))

		return actions

	def _count_face(self, face: int) -> int:
		assert self.state is not None
		count = 0
		for p in self.state.players:
			count += sum(1 for d in p.dice if d == face)
			if self.wild_ones and face != 1:
				count += sum(1 for d in p.dice if d == 1)
		return count

	def _resolve_challenge(self, challenger_idx: int) -> RoundResult:
		assert self.state is not None and self.state.current_bid is not None
		bid = self.state.current_bid
		actual = self._count_face(bid.face)
		bidder_idx = self._prev_player_idx(challenger_idx)
		# Determine winner/loser
		if actual >= bid.quantity:
			winner, loser = bidder_idx, challenger_idx
		else:
			winner, loser = challenger_idx, bidder_idx

		# Adjust dice
		self.state.players[loser].dice_remaining = max(0, self.state.players[loser].dice_remaining - 1)
		revealed_counts = {f: 0 for f in range(1, self.faces + 1)}
		for p in self.state.players:
			for d in p.dice:
				revealed_counts[d] += 1
		return RoundResult(
			winner_idx=winner,
			loser_idx=loser,
			revealed_counts=revealed_counts,
			resolved_on='challenge',
			bid=bid,
		)

	def _prev_player_idx(self, idx: int) -> int:
		assert self.state is not None
		n = len(self.state.players)
		return (idx - 1 + n) % n

	def play_game(self, verbose: bool = True) -> str:
		"""Runs until one player remains. Returns winner name."""
		self.start_new_game()
		assert self.state is not None

		while len([p for p in self.state.players if p.dice_remaining > 0]) > 1:
			self._begin_round()
			if verbose:
				print(f"\nRound {self.state.round_number} — dice in play: {self.state.total_dice_in_play()}")
				per_player = ", ".join(f"{p.name}={p.dice_remaining}" for p in self.state.players)
				print(f"Dice per player: {per_player}")

			# Round loop
			while True:
				idx = self.state.current_player_idx
				agent = self.state.players[idx].agent
				legal = self.legal_actions()
				action = agent.decide(self.state, legal)

				if action.kind == 'bid':
					# validate
					if action.bid is None or action not in legal:
						raise ValueError(f"Illegal bid by {agent.name}: {action}")
					self.state.current_bid = action.bid
					if verbose:
						print(f"{agent.name} bids {action.bid}")
					self.state.current_player_idx = self._next_player_idx(idx)
				elif action.kind == 'challenge':
					if self.state.current_bid is None:
						raise ValueError("Challenge without a current bid")
					if verbose:
						print(f"{agent.name} calls Dudo (challenge)")
					result = self._resolve_challenge(challenger_idx=idx)
					if verbose:
						print(
							f"Bid was {self.state.current_bid}, actual count: {self._count_face(self.state.current_bid.face)}. "
							f"Winner: {self.state.players[result.winner_idx].name}, Loser: {self.state.players[result.loser_idx].name}"
						)
					# End round
					# Determine if loser was eliminated before we filter
					loser_eliminated = self.state.players[result.loser_idx].dice_remaining == 0
					self._remove_eliminated()
					# Next round starts at loser; if eliminated, start at the player that now occupies that index
					self.state.current_player_idx = (
						min(result.loser_idx, len(self.state.players) - 1) if loser_eliminated else result.loser_idx
					)
					break
				elif action.kind == 'exact':
					if not self.exact_call_enabled or self.state.current_bid is None:
						raise ValueError("Exact call not allowed or no bid")
					# Simple exact rule: if exact, challenger gains one die (up to starting_dice), else loses one
					bid = self.state.current_bid
					actual = self._count_face(bid.face)
					if verbose:
						print(f"{agent.name} calls Exact")
					if actual == bid.quantity:
						self.state.players[idx].dice_remaining = min(
							self.starting_dice, self.state.players[idx].dice_remaining + 1
						)
						resolved_on = 'exact'
						winner_idx, loser_idx = idx, self._prev_player_idx(idx)
					else:
						self.state.players[idx].dice_remaining = max(0, self.state.players[idx].dice_remaining - 1)
						resolved_on = 'exact'
						winner_idx, loser_idx = self._prev_player_idx(idx), idx
					revealed_counts = {f: 0 for f in range(1, self.faces + 1)}
					for p in self.state.players:
						for d in p.dice:
							revealed_counts[d] += 1
					result = RoundResult(
						winner_idx=winner_idx,
						loser_idx=loser_idx,
						revealed_counts=revealed_counts,
						resolved_on=resolved_on,
						bid=self.state.current_bid,
					)
					if verbose:
						print(
							f"Bid was {self.state.current_bid}, actual count: {actual}. "
							f"Winner: {self.state.players[result.winner_idx].name}, Loser: {self.state.players[result.loser_idx].name}"
						)
					loser_eliminated = self.state.players[result.loser_idx].dice_remaining == 0
					self._remove_eliminated()
					self.state.current_player_idx = (
						min(result.loser_idx, len(self.state.players) - 1) if loser_eliminated else result.loser_idx
					)
					break
				else:
					raise ValueError(f"Unknown action: {action.kind}")

		# Winner
		assert self.state is not None
		winner = next(p.name for p in self.state.players if p.dice_remaining > 0)
		if verbose:
			print(f"\nWinner: {winner}")
		return winner


def demo_game() -> None:
	from agents import RandomAgent, ConservativeAgent

	engine = LiarDiceEngine(wild_ones=True, starting_dice=5)
	engine.add_players([
		RandomAgent("Alice"),
		ConservativeAgent("Bob"),
		RandomAgent("Cara"),
	])
	engine.play_game(verbose=True)


if __name__ == "__main__":
	demo_game()

