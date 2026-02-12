import importlib
import pkgutil
import random
from typing import List

from tqdm import tqdm

import agents
from game_engine import LiarDiceEngine
from models import Agent


class Simulation:
    def __init__(self, n_players_per_table:int=6, n_tables:int=10, n_replications:int=100):
        self.n_players_per_table = n_players_per_table
        self.n_tables = n_tables
        self.n_replications = n_replications
        self.agents = self._create_all_agents()
        self.global_scores = {p.name: 0 for p in self.agents}
        

    def start(self, verbose:bool=False, callback=None, return_history:bool=False):
        table_count = 0
        history = [] if return_history else None
        for table in self._make_tables():
            local_scores = {p.name: 0 for p in table}
            winner = "No winner"

            if verbose:
                print(f"Stating replications for table with following table:\n {[p.name for p in table]}")  

            for _ in tqdm(range(self.n_replications), desc=f"Replications for table {table_count} / {self.n_tables}"):
                engine = LiarDiceEngine(wild_ones=True, starting_dice=5)
                engine.add_players(table)
                winner = engine.play_game(verbose=False)
                if return_history:
                    history.append(winner)
                local_scores[winner] += 1
                self.global_scores[winner] += 1

                if callback:
                    callback(winner, self.global_scores)

            table_count += 1

            if verbose:
                print(f"{self.n_replications} replications have been finished. Scores at this table:\n{local_scores}\n\n")    

        if return_history:
            return self.global_scores, history        
        return self.global_scores


    def _make_tables(self):
        results = []
        for i in range(self.n_tables):
            results.append(self._recommend_permutation(self.agents, self.n_players_per_table))
        return results

    def _create_all_agents(self) -> List[Agent]:
        """
        Dynamically imports all modules in the agents package, finds all subclasses of Agent,
        and returns a list of their instances (with default constructors).
        """
        agent_instances = []
        for _, module_name, _ in pkgutil.iter_modules(agents.__path__):
            module = importlib.import_module(f"agents.{module_name}")
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Agent) and attr is not Agent:
                    agent_instances.append(attr())
        return agent_instances
    
    def _recommend_permutation(self, list:List, k_elem:int) -> List[Agent]:
        subset = random.sample(list, k_elem)
        random.shuffle(subset)
        return subset