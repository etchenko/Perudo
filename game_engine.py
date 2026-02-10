from __future__ import annotations

import math
import random
from typing import Callable, List, Optional, Sequence

from models import Action, Agent, Bid, GameState, PlayerState, RoundBid, RoundResult, RoundResolution


import signal
from contextlib import contextmanager

class TimeoutException(Exception): pass
# Utility context manager to enforce time limits on agent decisions
@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException("Timed out!")
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

class LiarDiceEngine:
	def __init__(
		self,
		faces: int = 6,
		starting_dice: int = 6,
		wild_ones: bool = True,
		exact_call_enabled: bool = True,
		rng: Optional[random.Random] = None,
		time_limit_seconds: int = 1,
	) -> None:
		self.faces = faces
		self.starting_dice = starting_dice
		self.wild_ones = wild_ones
		self.exact_call_enabled = exact_call_enabled
		self.rng = rng or random.Random()
		self.time_limit_seconds = time_limit_seconds
		self.agents: List[Agent] = []
		self.state: Optional[GameState] = None
		# Optional event listeners: functions receiving (event: str, payload: dict)
		self._listeners: List[Callable] = []

	def register_listener(self, listener: Callable) -> None:
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
			round_resolutions=[],
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

	def _capture_revealed_dice(self) -> dict[str, List[int]]:
		"""Capture all players' dice at resolution time"""
		assert self.state is not None
		return {p.name: list(p.dice) for p in self.state.players}

	def _record_bid(self, idx: int, bid: Bid) -> None:
		assert self.state is not None
		self.state.current_bid = bid
		rb = RoundBid(player_idx=idx, player_name=self.state.players[idx].name, bid=bid, round_number=self.state.round_number)
		self.state.round_bids.append(rb)
		self._emit("bid", player=self.state.players[idx].name, quantity=bid.quantity, face=bid.face)

	def is_action_legal(self, action: Action) -> bool:
		assert self.state is not None
		total = self.state.total_dice_in_play()
		cur = self.state.current_bid
		# Bid legality
		if action.kind == 'bid':
			b = action.bid
			if b is None:
				return False
			if not (1 <= b.face <= self.faces and 1 <= b.quantity <= total):
				return False
			if cur is None:
				return True
			# Wild ones rules
			if self.wild_ones:
				if b.face == 1:
					if cur.face == 1:
						return b.quantity > cur.quantity
					else:
						min_ones = math.ceil(cur.quantity / 2.0)
						return b.quantity >= min_ones
				elif cur.face == 1:
					min_quantity = cur.quantity * 2 + 1
					return b.quantity >= min_quantity
			# Standard rule
			return (b.quantity > cur.quantity) or (b.quantity == cur.quantity and b.face > cur.face)
		# Challenge legality
		if action.kind == 'challenge':
			return cur is not None
		# Exact legality
		if action.kind == 'exact':
			return self.exact_call_enabled and cur is not None
		return False

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

		# Capture revealed dice before adjusting
		revealed_dice = self._capture_revealed_dice()
		
		# Record the resolution
		resolution = RoundResolution(
			round_number=self.state.round_number,
			bids=list(self.state.round_bids),  # Copy all bids from this round
			final_bid=bid,
			resolution_type='challenge',
			resolver_name=self.state.players[challenger_idx].name,
			winner_name=self.state.players[winner].name,
			loser_name=self.state.players[loser].name,
			actual_count=actual,
			revealed_dice=revealed_dice,
		)
		self.state.round_resolutions.append(resolution)

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
		
		# Capture revealed dice before adjusting
		revealed_dice = self._capture_revealed_dice()
		
		# Correct exact: caller gains a die (capped), winner=caller
		if actual == bid.quantity:
			winner, loser = idx, self._prev_player_idx(idx)
			self.state.players[winner].dice_remaining = min(
				self.state.players[winner].dice_remaining + 1, self.starting_dice
			)
			self.state.players[loser].dice_remaining = max(0, self.state.players[loser].dice_remaining - 1)
		else:
			# Incorrect exact: caller loses, bidder wins
			winner, loser = self._prev_player_idx(idx), idx
			self.state.players[loser].dice_remaining = max(0, self.state.players[loser].dice_remaining - 1)
		
		# Record the resolution
		resolution = RoundResolution(
			round_number=self.state.round_number,
			bids=list(self.state.round_bids),  # Copy all bids from this round
			final_bid=bid,
			resolution_type='exact',
			resolver_name=self.state.players[idx].name,
			winner_name=self.state.players[winner].name,
			loser_name=self.state.players[loser].name,
			actual_count=actual,
			revealed_dice=revealed_dice,
		)
		self.state.round_resolutions.append(resolution)

		revealed_counts = self._compute_revealed_counts()
		return RoundResult(
			winner_idx=winner,
			loser_idx=loser,
			revealed_counts=revealed_counts,
			resolved_on='exact',
			bid=bid,
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
		# Show revealed dice
		revealed_parts = [f"{p.name}: {p.dice}" for p in self.state.players]
		print(f"Revealed dice: {', '.join(revealed_parts)}")
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


	def play_game(self, verbose: bool = True, max_round_turns: int = 200) -> str:
		"""Runs until one player remains. Returns winner name. Safeguard: max_round_turns per round."""
		self.start_new_game()
		assert self.state is not None

		while len([p for p in self.state.players if p.dice_remaining > 0]) > 1:
			self._begin_round()
			if verbose:
				print(f"\nRound {self.state.round_number} — dice in play: {self.state.total_dice_in_play()}")
				print(f"Dice per player: {self._format_dice_per_player()}")

			# Round loop

			turn_count = 0
			while True:
				turn_count += 1
				if turn_count > max_round_turns:
					# print(self.state.visible_summary_for(self.state.current_player_idx))
					raise Exception(f"Warning: round {self.state.round_number} exceeded {max_round_turns} turns.")
					

				idx = self.state.current_player_idx
				agent = self.state.players[idx].agent
				agent_obj = agent if isinstance(agent, Agent) else Agent()
				state_view = self.state.visible_summary_for(idx)
				try:
					with time_limit(self.time_limit_seconds): # 1 second per decision
						action = agent_obj.decide(state_view)
				except Exception:
					# Force challenge if timeout/error and a bid exists, else minimal legal bid
					print(f"Agent {agent_obj.name} timed out or errored on decision. Forcing legal fallback action.")
					if self.state.current_bid is not None:
						action = Action(kind='challenge')
					else:
						# Find minimal legal bid
						for q in range(1, self.state.total_dice_in_play() + 1):
							for f in range(1, self.faces + 1):
								min_bid = Bid(q, f)
								if self.is_action_legal(Action(kind='bid', bid=min_bid)):
									action = Action(kind='bid', bid=min_bid)
									break
								else:
									continue
							break

				if not self.is_action_legal(action):
					# Force challenge if illegal action and a bid exists, else minimal legal bid
					if self.state.current_bid is not None:
						action = Action(kind='challenge')
					else:
						# Find minimal legal bid
						for q in range(1, self.state.total_dice_in_play() + 1):
							for f in range(1, self.faces + 1):
								min_bid = Bid(q, f)
								if self.is_action_legal(Action(kind='bid', bid=min_bid)):
									action = Action(kind='bid', bid=min_bid)
									break
							else:
								continue
							break

				if action.kind == 'bid':
					if isinstance(action.bid, Bid):
						self._record_bid(idx, action.bid)
					if verbose:
						print(f"{agent_obj.name} bids {action.bid}")
					self.state.current_player_idx = self._next_player_idx(idx)
				elif action.kind == 'challenge':
					if self.state.current_bid is None:
						raise ValueError("Challenge without a current bid")
					if verbose:
						print(f"{agent_obj.name} calls Dudo (challenge)")
					result = self._resolve_challenge(challenger_idx=idx)
					self._print_resolution(result, actual=None, verbose=verbose)
					self._post_resolution_cleanup(result)
					break
				elif action.kind == 'exact':
					if not self.exact_call_enabled or self.state.current_bid is None:
						action = Action(kind='challenge')
						if verbose:
							print(f"{agent_obj.name} calls Dudo (challenge)")
						result = self._resolve_challenge(challenger_idx=idx)
						self._print_resolution(result, actual=None, verbose=verbose)
						self._post_resolution_cleanup(result)
						break
					if verbose:
						print(f"{agent_obj.name} calls Exact")
					result = self._resolve_exact(idx)
					actual = self._count_face(self.state.current_bid.face) if self.state.current_bid else None
					self._print_resolution(result, actual=actual, verbose=verbose)
					self._post_resolution_cleanup(result)
					break
				else:
					raise ValueError(f"Unknown action: {action.kind}")

		assert self.state is not None
		winner = next(p.name for p in self.state.players if p.dice_remaining > 0)
		if verbose:
			print(f"\nWinner: {winner}")
		self._emit("game_end", winner=winner)
		
		# Notify all agents that the game has finished
		for agent in self.agents:
			try:
				with time_limit(self.time_limit_seconds * 2): # 2 seconds for post-game processing
					agent.game_finished(winner, self.state.round_resolutions)
			except Exception:# Agent errors should not crash the engine
				pass
		
		return winner