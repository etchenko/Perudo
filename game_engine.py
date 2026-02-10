from __future__ import annotations

import random
from typing import List, Optional, Sequence

from models import Bid, Action, PlayerState, GameState, RoundResult, RoundBid
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
		# Optional event listeners: functions receiving (event: str, payload: dict)
		self._listeners: List[callable] = []

	def register_listener(self, listener: callable) -> None:
		self._listeners.append(listener)

	def _emit(self, event: str, **payload) -> None:
		for l in self._listeners:
			try:
				l(event, payload)
			except Exception:
				# Listener errors should not crash the engine
				pass

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
			round_bids=[],
		)

	def _begin_round(self) -> None:
		assert self.state is not None
		self.state.round_number += 1
		self.state.current_bid = None
		self.state.round_bids = []
		# Roll dice
		for p in self.state.players:
			p.dice = self._roll_dice_for(p.dice_remaining)
		# Emit round start
		self._emit(
			"round_start",
			round_number=self.state.round_number,
			total_dice=self.state.total_dice_in_play(),
			per_player=[{"name": p.name, "dice_remaining": p.dice_remaining} for p in self.state.players],
		)

	def _format_dice_per_player(self) -> str:
		assert self.state is not None
		return ", ".join(f"{p.name}={p.dice_remaining}" for p in self.state.players)

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

	def _compute_revealed_counts(self) -> dict:
		assert self.state is not None
		revealed_counts = {f: 0 for f in range(1, self.faces + 1)}
		for p in self.state.players:
			for d in p.dice:
				revealed_counts[d] += 1
		return revealed_counts

	def _record_bid(self, idx: int, bid: Bid) -> None:
		assert self.state is not None
		self.state.current_bid = bid
		self.state.round_bids.append(
			RoundBid(player_idx=idx, player_name=self.state.players[idx].name, bid=bid)
		)
		self._emit("bid", player=self.state.players[idx].name, quantity=bid.quantity, face=bid.face)

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
		revealed_counts = self._compute_revealed_counts()
		return RoundResult(
			winner_idx=winner,
			loser_idx=loser,
			revealed_counts=revealed_counts,
			resolved_on='challenge',
			bid=bid,
		)

	def _resolve_exact(self, idx: int) -> RoundResult:
		assert self.state is not None and self.state.current_bid is not None
		bid = self.state.current_bid
		actual = self._count_face(bid.face)
		# Correct exact: caller gains a die (capped), winner=caller
		if actual == bid.quantity:
			self.state.players[idx].dice_remaining = min(
				self.starting_dice, self.state.players[idx].dice_remaining + 1
			)
			winner_idx, loser_idx = idx, self._prev_player_idx(idx)
		else:
			self.state.players[idx].dice_remaining = max(0, self.state.players[idx].dice_remaining - 1)
			winner_idx, loser_idx = self._prev_player_idx(idx), idx
		revealed_counts = self._compute_revealed_counts()
		return RoundResult(
			winner_idx=winner_idx,
			loser_idx=loser_idx,
			revealed_counts=revealed_counts,
			resolved_on='exact',
			bid=self.state.current_bid,
		)

	def _post_resolution_cleanup(self, result: RoundResult) -> None:
		assert self.state is not None
		loser_eliminated = self.state.players[result.loser_idx].dice_remaining == 0
		if loser_eliminated:
			self._emit("player_eliminated", player=self.state.players[result.loser_idx].name)
		self._remove_eliminated()
		self.state.current_player_idx = (
			min(result.loser_idx, len(self.state.players) - 1) if loser_eliminated else result.loser_idx
		)

	def _print_resolution(self, result: RoundResult, actual: Optional[int], verbose: bool) -> None:
		if not verbose:
			return
		assert self.state is not None
		if actual is None and self.state.current_bid is not None:
			actual = self._count_face(self.state.current_bid.face)
		print(
			f"Bid was {self.state.current_bid}, actual count: {actual}. "
			f"Winner: {self.state.players[result.winner_idx].name}, Loser: {self.state.players[result.loser_idx].name}"
		)
		self._emit(
			"challenge_resolved" if result.resolved_on == "challenge" else "exact_resolved",
			winner=self.state.players[result.winner_idx].name,
			loser=self.state.players[result.loser_idx].name,
			bid={"quantity": self.state.current_bid.quantity, "face": self.state.current_bid.face} if self.state.current_bid else None,
			actual=actual,
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
				print(f"Dice per player: {self._format_dice_per_player()}")

			# Round loop
			while True:
				idx = self.state.current_player_idx
				agent = self.state.players[idx].agent
				legal = self.legal_actions()
				state_view = self.state.visible_summary_for(idx)
				action = agent.decide(state_view, legal)

				if action.kind == 'bid':
					# validate
					if action.bid is None or action not in legal:
						raise ValueError(f"Illegal bid by {agent.name}: {action}")
					self._record_bid(idx, action.bid)
					if verbose:
						print(f"{agent.name} bids {action.bid}")
					self.state.current_player_idx = self._next_player_idx(idx)
				elif action.kind == 'challenge':
					if self.state.current_bid is None:
						raise ValueError("Challenge without a current bid")
					if verbose:
						print(f"{agent.name} calls Dudo (challenge)")
					result = self._resolve_challenge(challenger_idx=idx)
					self._print_resolution(result, actual=None, verbose=verbose)
					self._post_resolution_cleanup(result)
					break
				elif action.kind == 'exact':
					if not self.exact_call_enabled or self.state.current_bid is None:
						raise ValueError("Exact call not allowed or no bid")
					if verbose:
						print(f"{agent.name} calls Exact")
					result = self._resolve_exact(idx)
					# For exact we can compute actual for print
					actual = self._count_face(self.state.current_bid.face) if self.state.current_bid else None
					self._print_resolution(result, actual=actual, verbose=verbose)
					self._post_resolution_cleanup(result)
					break
				else:
					raise ValueError(f"Unknown action: {action.kind}")

		# Winner
		assert self.state is not None
		winner = next(p.name for p in self.state.players if p.dice_remaining > 0)
		if verbose:
			print(f"\nWinner: {winner}")
		self._emit("game_end", winner=winner)
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

