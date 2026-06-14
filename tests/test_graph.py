import unittest

from enterprise_rag.graph import PipelineGraph, PipelineState
from enterprise_rag.models import QueryIntent


class GraphEngineTest(unittest.TestCase):
    def test_linear_execution(self) -> None:
        graph = PipelineGraph()
        
        def node1(state: PipelineState) -> PipelineState:
            state.route_reason = "node1_visited"
            return state

        def node2(state: PipelineState) -> PipelineState:
            state.route_reason += "_node2_visited"
            return state

        graph.add_node("n1", node1)
        graph.add_node("n2", node2)
        graph.add_edge("n1", "n2")
        graph.set_entry_point("n1")

        initial_state = PipelineState(user_id="u1", query="q")
        final_state = graph.execute(initial_state)

        self.assertEqual(final_state.route_reason, "node1_visited_node2_visited")

    def test_conditional_execution(self) -> None:
        graph = PipelineGraph()

        def start_node(state: PipelineState) -> PipelineState:
            return state

        def factual_node(state: PipelineState) -> PipelineState:
            state.route_reason = "went_factual"
            return state

        def other_node(state: PipelineState) -> PipelineState:
            state.route_reason = "went_other"
            return state

        graph.add_node("start", start_node)
        graph.add_node("factual", factual_node)
        graph.add_node("other", other_node)

        graph.add_conditional_edge("start", "factual", lambda state: state.intent == QueryIntent.FACTUAL)
        graph.add_conditional_edge("start", "other", lambda state: state.intent != QueryIntent.FACTUAL)
        
        graph.set_entry_point("start")

        # Test true branch
        state_factual = PipelineState(user_id="u", query="q", intent=QueryIntent.FACTUAL)
        res1 = graph.execute(state_factual)
        self.assertEqual(res1.route_reason, "went_factual")

        # Test false branch
        state_other = PipelineState(user_id="u", query="q", intent=QueryIntent.EXPLORATORY)
        res2 = graph.execute(state_other)
        self.assertEqual(res2.route_reason, "went_other")

    def test_short_circuit(self) -> None:
        graph = PipelineGraph()

        def check_node(state: PipelineState) -> PipelineState:
            state.short_circuited = True
            return state

        def never_node(state: PipelineState) -> PipelineState:
            state.route_reason = "should_not_run"
            return state

        graph.add_node("check", check_node)
        graph.add_node("never", never_node)
        graph.add_edge("check", "never")
        graph.set_entry_point("check")

        initial_state = PipelineState(user_id="u", query="q")
        final_state = graph.execute(initial_state)

        self.assertEqual(final_state.route_reason, "")
        self.assertTrue(final_state.short_circuited)


if __name__ == "__main__":
    unittest.main()
