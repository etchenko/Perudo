import unittest
from typing import List, Mapping, Any, Sequence

from models import Bid, Action, PlayerState, GameState, RoundBid
from game_engine import LiarDiceEngine


class ScriptedAgent:
    """Agent that plays a scripted sequence of actions."""
    def __init__(self, name: str, script: List[Action]):
        self.name = name
        self._script = list(script)

    def decide(self, state_view, *args, **kwargs) -> Action:
        if not self._script:
            # default to challenge if possible, else minimal bid
            return Action(kind='challenge') if state_view.current_bid else Action(kind='bid', bid=Bid(1, 1))
        desired = self._script.pop(0)
        return desired


class DeterministicEngine(LiarDiceEngine):
    """Expose a single-round play method for testing with fixed dice."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fixed_dice = None

    def set_round_dice(self, dice_per_player):
        self._fixed_dice = [list(d) for d in dice_per_player]

    def _begin_round(self):
        assert self.state is not None
        self.state.round_number += 1
        self.state.current_bid = None
        self.state.round_bids = []
        if self._fixed_dice is not None:
            for i, p in enumerate(self.state.players):
                p.dice = list(self._fixed_dice[i])
        else:
            for p in self.state.players:
                p.dice = self._roll_dice_for(p.dice_remaining)

    def play_one_round(self, verbose: bool = False):
        assert self.state is not None
        self._begin_round()
        if verbose:
            print(f"\nRound {self.state.round_number} — dice in play: {self.state.total_dice_in_play()}")
            per_player = ", ".join(f"{p.name}={p.dice_remaining}" for p in self.state.players)
            print(f"Dice per player: {per_player}")
        while True:
            idx = self.state.current_player_idx
            agent = self.state.players[idx].agent
            view = self.state.visible_summary_for(idx)
            action = agent.decide(view)
            if action.kind == 'bid':
                if action.bid is None or not self.is_action_legal(action):
                    if self.state.current_bid is not None:
                        action = Action(kind='challenge')
                    else:
                        # choose minimal legal bid
                        min_bid = min((a.bid for a in legal if a.kind == 'bid' and a.bid), key=lambda b: (b.quantity, b.face))
                        action = Action(kind='bid', bid=min_bid)
                if action.kind == 'bid':
                    self.state.current_bid = action.bid
                    rb = RoundBid(player_idx=idx, player_name=self.state.players[idx].name, bid=action.bid, round_number=self.state.round_number)
                    self.state.round_bids.append(rb)
                    self.state.current_player_idx = (idx + 1) % len(self.state.players)
                else:
                    # fallthrough to challenge
                    pass
            elif action.kind == 'challenge':
                if self.state.current_bid is None:
                    raise ValueError("Challenge without bid")
                # Resolve using base method
                result = self._resolve_challenge(challenger_idx=idx)
                # Emit resolution event similar to engine
                actual = self._count_face(self.state.current_bid.face)
                self._emit(
                    "challenge_resolved",
                    winner=self.state.players[result.winner_idx].name,
                    loser=self.state.players[result.loser_idx].name,
                    bid={"quantity": self.state.current_bid.quantity, "face": self.state.current_bid.face},
                    actual=actual,
                )
                loser_eliminated = self.state.players[result.loser_idx].dice_remaining == 0
                if loser_eliminated:
                    self._emit("player_eliminated", player=self.state.players[result.loser_idx].name)
                self._remove_eliminated()
                self.state.current_player_idx = (
                    min(result.loser_idx, len(self.state.players) - 1) if loser_eliminated else result.loser_idx
                )
                break
            elif action.kind == 'exact':
                if not self.exact_call_enabled or self.state.current_bid is None:
                    raise ValueError("Exact call not allowed or no bid")
                result = self._resolve_exact(idx)
                actual = self._count_face(self.state.current_bid.face)
                self._emit(
                    "exact_resolved",
                    winner=self.state.players[result.winner_idx].name,
                    loser=self.state.players[result.loser_idx].name,
                    bid={"quantity": self.state.current_bid.quantity, "face": self.state.current_bid.face},
                    actual=actual,
                )
                loser_eliminated = self.state.players[result.loser_idx].dice_remaining == 0
                if loser_eliminated:
                    self._emit("player_eliminated", player=self.state.players[result.loser_idx].name)
                self._remove_eliminated()
                self.state.current_player_idx = (
                    min(result.loser_idx, len(self.state.players) - 1) if loser_eliminated else result.loser_idx
                )
                break
            else:
                raise ValueError("Unsupported in test")


class LiarDiceTests(unittest.TestCase):
    def test_count_face_without_wild_ones(self):
        # Setup a minimal state
        players = [
            PlayerState(name='A', dice_remaining=3, dice=[1, 2, 3], agent=None),
            PlayerState(name='B', dice_remaining=3, dice=[1, 2, 2], agent=None),
        ]
        state = GameState(players=players, current_player_idx=0, current_bid=None, round_number=1, faces=6, wild_ones=False, round_bids=[], round_resolutions=[])
        engine = LiarDiceEngine(wild_ones=False)
        engine.state = state
        self.assertEqual(engine._count_face(2), 3)  # only 2s count

    def test_count_face_with_wild_ones(self):
        players = [
            PlayerState(name='A', dice_remaining=3, dice=[1, 2, 3], agent=None),
            PlayerState(name='B', dice_remaining=3, dice=[1, 2, 2], agent=None),
        ]
        state = GameState(players=players, current_player_idx=0, current_bid=None, round_number=1, faces=6, wild_ones=True, round_bids=[], round_resolutions=[])
        engine = LiarDiceEngine(wild_ones=True)
        engine.state = state
        self.assertEqual(engine._count_face(2), 5)  # 2s + ones count
        self.assertEqual(engine._count_face(1), 2)  # ones only for face=1

    def test_round_bids_history_records(self):
        # Two players. A bids, B challenges.
        a = ScriptedAgent('A', [Action(kind='bid', bid=Bid(1, 2))])
        b = ScriptedAgent('B', [Action(kind='challenge')])
        engine = DeterministicEngine(wild_ones=False, starting_dice=3)
        engine.add_players([a, b])
        engine.start_new_game()
        # Fix dice manually for predictability
        engine.set_round_dice([
            [2, 3, 4],
            [1, 6, 6],
        ])
        engine.play_one_round(verbose=False)
        self.assertEqual(len(engine.state.round_bids), 1)
        rb = engine.state.round_bids[0]
        self.assertEqual(rb.player_name, 'A')
        self.assertEqual(rb.bid.quantity, 1)
        self.assertEqual(rb.bid.face, 2)

    def test_index_clamp_on_elimination(self):
        # Three players: P0 bids, P1 bids, P2 bids false, P0 challenges and P2 loses (eliminated)
        p0 = ScriptedAgent('P0', [Action(kind='bid', bid=Bid(1, 2)), Action(kind='challenge')])
        p1 = ScriptedAgent('P1', [Action(kind='bid', bid=Bid(1, 5))])
        p2 = ScriptedAgent('P2', [Action(kind='bid', bid=Bid(1, 6))])
        engine = DeterministicEngine(wild_ones=False, starting_dice=1)
        engine.add_players([p0, p1, p2])
        engine.start_new_game()
        # Ensure last player has 1 die and will be bidder then eliminated
        engine.state.players[2].dice_remaining = 1
        # Dice contain no 6 so P2's bid 1x6 is false; P0 then challenges and P2 loses
        engine.set_round_dice([
            [2],
            [5],
            [4],
        ])
        # Play one round; P2 bids false, P0 challenges, P2 eliminated
        engine.play_one_round(verbose=False)
        # After removal, current_player_idx must be valid and not out of range
        self.assertTrue(0 <= engine.state.current_player_idx < len(engine.state.players))
        # P2 eliminated
        self.assertEqual(len(engine.state.players), 2)
        names = [p.name for p in engine.state.players]
        self.assertNotIn('P2', names)

    def test_agent_receives_partial_view(self):
        class InspectingAgent:
            def __init__(self, name):
                self.name = name
                self.checked = False
                self.call_count = 0

            def decide(self, state_view):
                # Ensure players entries do not expose dice lists
                players = state_view.players
                for entry in players:
                    assert not hasattr(entry, 'dice')
                # Ensure my_dice exists and is a list of ints
                my_dice = state_view.my_dice
                assert isinstance(my_dice, list)
                assert all(isinstance(d, int) for d in my_dice)
                # Ensure round_bids is present
                assert isinstance(state_view.round_bids, list)
                # Ensure round_resolutions is present
                assert isinstance(state_view.round_resolutions, list)
                self.checked = True
                self.call_count += 1
                # First call bids, second call challenges to end round
                if self.call_count == 1:
                    return Action(kind='bid', bid=Bid(1, 2))
                else:
                    return Action(kind='challenge')

        a0 = InspectingAgent('A')
        a1 = InspectingAgent('B')
        engine = DeterministicEngine(wild_ones=True, starting_dice=2)
        engine.add_players([a0, a1])
        engine.start_new_game()
        engine.set_round_dice([
            [1, 2],
            [2, 3],
        ])
        engine.play_one_round(verbose=False)
        # Both agents should have been called and checked
        self.assertTrue(a0.checked)
        self.assertTrue(a1.checked)

    def test_legal_actions_initial_all_bids(self):
        engine = DeterministicEngine(wild_ones=False, starting_dice=2, faces=6)
        # two players => 4 dice total
        a = ScriptedAgent('A', [])
        b = ScriptedAgent('B', [])
        engine.add_players([a, b])
        engine.start_new_game()
        engine.set_round_dice([
            [1, 2],
            [3, 4],
        ])
        engine._begin_round()
        # Test that bids are legal when no current bid exists
        self.assertTrue(engine.is_action_legal(Action(kind='bid', bid=Bid(1, 1))))
        self.assertTrue(engine.is_action_legal(Action(kind='bid', bid=Bid(4, 6))))
        # Verify challenge and exact are not legal when no current bid
        self.assertFalse(engine.is_action_legal(Action(kind='challenge')))
        self.assertFalse(engine.is_action_legal(Action(kind='exact')))

    def test_legal_actions_with_current_bid_and_exact_toggle(self):
        # Setup with 5 dice total
        engine = DeterministicEngine(wild_ones=False, starting_dice=3, faces=6, exact_call_enabled=True)
        x = ScriptedAgent('X', [])
        y = ScriptedAgent('Y', [])
        engine.add_players([x, y])
        engine.start_new_game()
        engine.set_round_dice([
            [1, 2, 3],
            [4, 5],
        ])
        engine._begin_round()
        # Set a current bid 2x3
        engine.state.current_bid = Bid(2, 3)
        # Test some legal bids (higher quantity or same quantity higher face)
        self.assertTrue(engine.is_action_legal(Action(kind='bid', bid=Bid(3, 1))))
        self.assertTrue(engine.is_action_legal(Action(kind='bid', bid=Bid(2, 4))))
        # Test illegal bids
        self.assertFalse(engine.is_action_legal(Action(kind='bid', bid=Bid(2, 3))))
        self.assertFalse(engine.is_action_legal(Action(kind='bid', bid=Bid(1, 6))))
        # Challenge and exact are legal
        self.assertTrue(engine.is_action_legal(Action(kind='challenge')))
        self.assertTrue(engine.is_action_legal(Action(kind='exact')))

        # Now disable exact and verify it's not legal
        engine.exact_call_enabled = False
        self.assertTrue(engine.is_action_legal(Action(kind='challenge')))
        self.assertFalse(engine.is_action_legal(Action(kind='exact')))

    def test_exact_call_correct_and_incorrect(self):
        # Listener to capture events
        events = []
        def collect(event, payload):
            events.append((event, payload))

        # Correct exact: set bid to match actual
        a = ScriptedAgent('A', [Action(kind='bid', bid=Bid(2, 2))])
        b = ScriptedAgent('B', [Action(kind='exact')])
        engine = DeterministicEngine(wild_ones=False, starting_dice=3, faces=6, exact_call_enabled=True)
        engine.add_players([a, b])
        engine.start_new_game()
        engine.register_listener(collect)
        engine.set_round_dice([
            [2, 5, 6],
            [2, 3, 4],
        ])
        engine.play_one_round(verbose=False)
        # B should gain one die (capped to starting_dice)
        b_state = next(p for p in engine.state.players if p.name == 'B')
        self.assertEqual(b_state.dice_remaining, 3)
        self.assertTrue(any(e[0] == 'exact_resolved' for e in events))

        # Incorrect exact: set bid not matching actual
        events.clear()
        a2 = ScriptedAgent('A2', [Action(kind='bid', bid=Bid(1, 6))])
        b2 = ScriptedAgent('B2', [Action(kind='exact')])
        engine2 = DeterministicEngine(wild_ones=False, starting_dice=1, faces=6, exact_call_enabled=True)
        engine2.add_players([a2, b2])
        engine2.start_new_game()
        engine2.register_listener(collect)
        engine2.set_round_dice([
            [2],
            [3],
        ])
        engine2.play_one_round(verbose=False)
        # B2 should lose one die and be eliminated
        names2 = [p.name for p in engine2.state.players]
        self.assertNotIn('B2', names2)
        self.assertTrue(any(e[0] == 'player_eliminated' for e in events))

    def test_bid_ordering_strictly_increasing(self):
        engine = DeterministicEngine(wild_ones=False, starting_dice=2, faces=6)
        a = ScriptedAgent('A', [])
        b = ScriptedAgent('B', [])
        engine.add_players([a, b])
        engine.start_new_game()
        engine.set_round_dice([
            [1, 2],
            [3, 4],
        ])
        engine._begin_round()
        engine.state.current_bid = Bid(2, 3)
        # Test some legal bids (strictly higher)
        legal_bids = [
            Bid(3, 1), Bid(3, 2), Bid(4, 1),  # Higher quantity
            Bid(2, 4), Bid(2, 5), Bid(2, 6),  # Same quantity, higher face
        ]
        for bid in legal_bids:
            self.assertTrue(engine.is_action_legal(Action(kind='bid', bid=bid)))
        # Test illegal bids
        illegal_bids = [
            Bid(2, 3),  # Same as current
            Bid(2, 2),  # Same quantity, lower face
            Bid(1, 6),  # Lower quantity
        ]
        for bid in illegal_bids:
            self.assertFalse(engine.is_action_legal(Action(kind='bid', bid=bid)))


if __name__ == '__main__':
    unittest.main()
