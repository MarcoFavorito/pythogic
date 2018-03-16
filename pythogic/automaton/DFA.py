from typing import FrozenSet, Dict, Tuple, Iterable, List
import graphviz
from copy import deepcopy

from pythogic.automaton.misc import Sink
from pythogic.base.Alphabet import Alphabet
from pythogic.base.Symbol import Symbol
from pythogic.base.utils import my_str


def _check_same_type(i: Iterable):
    l = list(i)
    return len(l) > 0 and not all(type(l[0]) == symbol for symbol in l[1:])


class DFA(object):

    def __init__(self, alphabet: Alphabet, states: FrozenSet, initial_state, accepting_states: FrozenSet,
                 transition_function: Dict[object, Dict[Symbol, object]]):
        self._check_input(alphabet, states, initial_state, accepting_states, transition_function)

        self.alphabet = alphabet
        self.states = states
        self.initial_state = initial_state
        self.accepting_states = accepting_states
        self.transition_function = transition_function

    def _check_input(self, alphabet, states, initial_state, accepting_states, transition_function):
        if initial_state and initial_state not in states:
            raise ValueError
        if any(not s in states for s in accepting_states):
            raise ValueError
        for s, sym2state in transition_function.items():
            if s not in states or any(sym not in alphabet.symbols and next_state not in states for sym, next_state in sym2state.items()):
                raise ValueError

    @classmethod
    def complete(cls, dfa):
        sink = Sink()
        transitions = deepcopy(dfa.transition_function)
        for state, sym2state in dfa.transition_function.items():
            for action in dfa.alphabet.symbols:
                if not action in sym2state:
                    transitions[state][action]= sink
        return DFA(dfa.alphabet, dfa.states.union({sink}), dfa.initial_state, dfa.accepting_states,
                   dict(transitions))

    @classmethod
    def minimize(cls, orig_dfa):
        dfa = DFA.complete(orig_dfa)

        # Greatest−fixpoint
        z_current = set()
        z_next = set()
        for state_s in dfa.states:
            for state_t in dfa.states:
                if state_s in dfa.accepting_states and state_t in dfa.accepting_states \
                    or state_s not in dfa.accepting_states and state_t not in dfa.accepting_states:
                    z_next.add((state_s, state_t))

        while z_current != z_next:
            z_current = z_next
            z_next = deepcopy(z_current)
            for (s, t) in z_current:
                for a in dfa.alphabet.symbols:
                    s_prime = dfa.transition_function[s][a] if s in dfa.transition_function and a in dfa.transition_function[s] else None
                    if s_prime and not any(
                        dfa.transition_function[t][a]==t_prime and (s_prime, t_prime) in z_current
                        for t_prime in dfa.states if t in dfa.transition_function):
                        z_next.remove((s,t))
                        break

                    t_prime = dfa.transition_function[t][a] if t in dfa.transition_function and a in dfa.transition_function[t] else None
                    if t_prime and not any(
                        dfa.transition_function[s][a] == s_prime and (s_prime, t_prime) in z_current
                        for s_prime in dfa.states if s in dfa.transition_function):
                        z_next.remove((s, t))
                        break

        state2equiv_class = dict()
        for (s, t) in z_current:
            state2equiv_class.setdefault(s, set()).add(t)
        state2equiv_class = {k: frozenset(v) for k,v in state2equiv_class.items()}

        equivalence_classes = set(map(frozenset,state2equiv_class.values()))
        equiv_class2new_state = dict([(ec, i) for i, ec in enumerate(equivalence_classes)])

        new_transition_function = {}
        for state in dfa.transition_function:
            new_state = equiv_class2new_state[state2equiv_class[state]]
            for action, next_state in dfa.transition_function[state].items():
                new_next_state = equiv_class2new_state[state2equiv_class[next_state]]
                new_transition_function.setdefault(new_state, {})
                new_transition_function[new_state][action] = new_next_state

        new_final_states = frozenset(s for s in set(equiv_class2new_state[state2equiv_class[old_state]] for old_state in  dfa.accepting_states))

        return DFA(dfa.alphabet, frozenset(equiv_class2new_state.values()), equiv_class2new_state[state2equiv_class[dfa.initial_state]], new_final_states, new_transition_function)

    @classmethod
    def reachable(cls, dfa):

        # least fixpoint
        z_current, z_next = set(), set()
        z_next.add(dfa.initial_state)

        while z_current != z_next:
            z_current = z_next
            z_next = deepcopy(z_current)
            for s in z_current:
                for a in dfa.transition_function.get(s, []):
                    next_state = dfa.transition_function[s][a]
                    z_next.add(next_state)

        new_states = z_current
        new_transition_function = {}
        for s in new_states:
            for a in dfa.transition_function.get(s, []):
                next_state = dfa.transition_function[s][a]
                if next_state in new_states:
                    new_transition_function.setdefault(s, {})
                    new_transition_function[s].setdefault(a, {})
                    new_transition_function[s][a] = next_state

        new_final_states = frozenset(new_states.intersection(dfa.accepting_states))

        return DFA(dfa.alphabet, new_states, dfa.initial_state, new_final_states, new_transition_function)

    @classmethod
    def coreachable(cls, dfa):
        # least fixpoint
        z_current, z_next = set(), set()
        z_next = set(dfa.accepting_states)

        while z_current != z_next:
            z_current = z_next
            z_next = deepcopy(z_current)
            for state in dfa.states:
                for a in dfa.transition_function.get(state, []):
                    next_state = dfa.transition_function[state][a]
                    if next_state in z_next:
                        z_next.add(state)
                        break

        new_states = z_current
        new_transition_function = {}
        for s in new_states:
            for a in dfa.transition_function.get(s, []):
                next_state = dfa.transition_function[s][a]
                if next_state in new_states:
                    new_transition_function.setdefault(s, {})
                    new_transition_function[s].setdefault(a, {})
                    new_transition_function[s][a] = next_state

        if dfa.initial_state not in new_states:
            initial_state = None
        else:
            initial_state = dfa.initial_state
        return DFA(dfa.alphabet, new_states, initial_state, dfa.accepting_states, new_transition_function)



    @classmethod
    def trim(cls, dfa):
        dfa = DFA.reachable(dfa)
        dfa = DFA.coreachable(dfa)
        return dfa


    def word_acceptance(self, word:List[Symbol]):
        assert all(char in self.alphabet.symbols for char in word)
        current_state = self.initial_state
        for char in word:
            if char not in self.transition_function[current_state]:
                return False
            else:
                current_state = self.transition_function[current_state][char]
        return current_state in self.accepting_states


    def to_dot(self, path):
        str = my_str
        g = graphviz.Digraph(format='svg')
        g.node('fake', style='invisible')
        for state in self.states:
            if state == self.initial_state:
                if state in self.accepting_states:
                    g.node(str(state), root='true',
                           shape='doublecircle')
                else:
                    g.node(str(state), root='true')
            elif state in self.accepting_states:
                g.node(str(state), shape='doublecircle')
            else:
                g.node(str(state))

        g.edge('fake', str(self.initial_state), style='bold')
        for state, sym2state in self.transition_function.items():
            for sym, next_state in sym2state.items():
                g.edge(str(state),
                   str(next_state),
                   label=str(sym))

        # if not os.path.exists(path):
        #     os.makedirs(path)

        g.render(filename=path)
        return

