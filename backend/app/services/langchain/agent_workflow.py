"""LangGraph-based multi-step reasoning agent workflow.

Implements a StateGraph that classifies incoming queries, routes them to
the appropriate processing path (simple retrieval, multi-step reasoning,
or clarification), and manages conversation state across turns.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Literal

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from app.services.langchain.rag_chain import RAGChain

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """Typed state for the agent workflow."""

    query: str
    session_id: str
    conversation_history: list[dict[str, str]]
    retrieved_context: list[Any]
    intermediate_steps: list[str]
    sub_questions: list[str]
    final_answer: str
    source_attributions: list[dict]
    retrieval_metadata: dict
    token_usage: dict
    response_type: str  # "answer" | "clarification"
    step_count: int
    step_limit_reached: bool


_CLASSIFICATION_PROMPT = """\
You are a query classifier for a business knowledge base system containing product data \
(master barang), outlet data, and distributor/vendor data.

Classify the user's query into exactly one of these categories:

1. "simple_retrieval" - The query can be answered with a single retrieval from \
the knowledge base. Examples: factual questions, lookups, comparisons, filtering, \
min/max questions, price questions, product attribute lookups, vendor queries, \
listing products meeting a criteria (e.g., price range, weight, unit type), \
counting items in a category.

2. "multi_step" - The query requires breaking down into multiple sub-questions \
or reasoning steps that COMBINE different types of data. Examples: calculations \
requiring multiple data points from different sheets, questions that need vendor \
info AND product list together, comparing unit prices across products.

3. "clarification" - ONLY use this if the query is truly unrelated to the knowledge \
base content (not about products, outlets, or vendors) AND is too vague to interpret. \
NEVER classify product/business data questions as clarification - always try \
simple_retrieval or multi_step first.

IMPORTANT RULES:
- Questions asking "apa saja produk yang..." (what products...), "list/daftar produk...", \
"produk mana yang..." (which products...) → ALWAYS simple_retrieval
- Questions about "produk termahal", "produk termurah", "harga jual paling mahal/murah" → simple_retrieval
- Questions about "berapa jumlah", "berapa banyak", "total" → simple_retrieval
- Questions about filtering (harga di antara X dan Y, berat di atas X) → simple_retrieval
- Questions asking "satuan produk Y" or product attributes → simple_retrieval
- Only use multi_step when the query genuinely requires COMBINING data from different sheets

Conversation history (if any):
{history}

User query: {query}

Respond with ONLY one of: simple_retrieval, multi_step, clarification
"""

_DECOMPOSITION_PROMPT = """\
You are a query decomposition assistant. Break down the following complex query \
into simpler sub-questions that can each be answered independently from a \
knowledge base.

Rules:
- Generate at most 5 sub-questions
- Each sub-question should be self-contained and answerable independently
- Sub-questions should collectively cover all aspects of the original query
- Return the sub-questions as a JSON array of strings

Conversation history (if any):
{history}

Original query: {query}

Respond with ONLY a JSON array of strings, e.g.: ["question 1", "question 2"]
"""

_SYNTHESIS_PROMPT = """\
You are a synthesis assistant. Combine the following intermediate answers into \
a single coherent response that addresses the original query.

Rules:
- Synthesize information from all intermediate answers
- Maintain source attributions where applicable
- Be concise and direct
- Only use information from the provided intermediate answers
- {language_instruction}

Original query: {query}

Intermediate answers:
{intermediate_answers}

Provide a synthesized answer:
"""

_CLARIFICATION_PROMPT = """\
You are a helpful assistant. The user's query is too vague or ambiguous to \
answer directly. Generate a clarifying question to help understand what they need.
{language_instruction}

Conversation history (if any):
{history}

User query: {query}

Generate a brief, helpful clarifying question:
"""

_LANGUAGE_INSTRUCTIONS = {
    "id": "You MUST respond in Bahasa Indonesia.",
    "en": "You MUST respond in English.",
}


class AgentWorkflow:
    """LangGraph-based multi-step reasoning workflow.

    Classifies incoming queries and routes them through the appropriate
    processing path: simple retrieval, multi-step reasoning with
    decomposition, or clarification request.

    Args:
        llm: A LangChain BaseChatModel instance for classification and synthesis.
        rag_chain: A RAGChain instance for document retrieval and generation.
    """

    MAX_STEPS: int = 5
    MAX_HISTORY_TURNS: int = 20

    def __init__(self, llm: "BaseChatModel", rag_chain: "RAGChain", language: str = "id") -> None:
        self.llm = llm
        self.rag_chain = rag_chain
        self.language = language
        self._session_store: "SessionStore | None" = None
        self._graph = self.compile()

    @property
    def session_store(self) -> "SessionStore":
        """Lazy-initialize the session store."""
        if self._session_store is None:
            from app.services.langchain.session_store import SessionStore

            self._session_store = SessionStore()
        return self._session_store

    @session_store.setter
    def session_store(self, store: "SessionStore") -> None:
        """Allow injection of a session store (useful for testing)."""
        self._session_store = store

    def compile(self) -> Any:
        """Build and compile the LangGraph StateGraph.

        Returns:
            A compiled LangGraph application (runnable).
        """
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("classify_query", self._classify_query)
        graph.add_node("simple_retrieval", self._simple_retrieval)
        graph.add_node("decompose_query", self._decompose_query)
        graph.add_node("retrieve_sub_question", self._retrieve_sub_question)
        graph.add_node("synthesize_answer", self._synthesize_answer)
        graph.add_node("generate_clarification", self._generate_clarification)

        # Set entry point
        graph.set_entry_point("classify_query")

        # Add conditional edge after classification
        graph.add_conditional_edges(
            "classify_query",
            self._route_after_classification,
            {
                "simple_retrieval": "simple_retrieval",
                "decompose_query": "decompose_query",
                "generate_clarification": "generate_clarification",
            },
        )

        # Simple retrieval goes to END
        graph.add_edge("simple_retrieval", END)

        # Decompose query leads to retrieve sub-questions
        graph.add_edge("decompose_query", "retrieve_sub_question")

        # After retrieving sub-questions, check if we should continue
        graph.add_conditional_edges(
            "retrieve_sub_question",
            self._should_continue_reasoning,
            {
                "synthesize": "synthesize_answer",
                "continue": "retrieve_sub_question",
            },
        )

        # Synthesize answer goes to END
        graph.add_edge("synthesize_answer", END)

        # Clarification goes to END
        graph.add_edge("generate_clarification", END)

        return graph.compile()

    def invoke(self, query: str, session_id: str = "") -> AgentState:
        """Synchronously run the agent workflow.

        Loads conversation history from the session store, runs the graph,
        and saves the new turn to the session store.

        Args:
            query: The user's question.
            session_id: Optional session identifier for multi-turn conversations.

        Returns:
            The final AgentState with the answer and metadata.
        """
        # Load conversation history
        conversation_history: list[dict[str, str]] = []
        if session_id:
            conversation_history = self.session_store.get_history(session_id)

        # Build initial state
        initial_state: AgentState = {
            "query": query,
            "session_id": session_id,
            "conversation_history": conversation_history,
            "retrieved_context": [],
            "intermediate_steps": [],
            "sub_questions": [],
            "final_answer": "",
            "source_attributions": [],
            "retrieval_metadata": {},
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "response_type": "answer",
            "step_count": 0,
            "step_limit_reached": False,
        }

        # Run the graph
        result = self._graph.invoke(initial_state)

        # Save turn to session store
        if session_id:
            self.session_store.add_turn(session_id, "user", query)
            self.session_store.add_turn(session_id, "assistant", result["final_answer"])

        return result

    async def ainvoke(self, query: str, session_id: str = "") -> AgentState:
        """Asynchronously run the agent workflow.

        Loads conversation history from the session store, runs the graph,
        and saves the new turn to the session store.

        Args:
            query: The user's question.
            session_id: Optional session identifier for multi-turn conversations.

        Returns:
            The final AgentState with the answer and metadata.
        """
        # Load conversation history
        conversation_history: list[dict[str, str]] = []
        if session_id:
            conversation_history = self.session_store.get_history(session_id)

        # Build initial state
        initial_state: AgentState = {
            "query": query,
            "session_id": session_id,
            "conversation_history": conversation_history,
            "retrieved_context": [],
            "intermediate_steps": [],
            "sub_questions": [],
            "final_answer": "",
            "source_attributions": [],
            "retrieval_metadata": {},
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "response_type": "answer",
            "step_count": 0,
            "step_limit_reached": False,
        }

        # Run the graph asynchronously
        result = await self._graph.ainvoke(initial_state)

        # Save turn to session store
        if session_id:
            self.session_store.add_turn(session_id, "user", query)
            self.session_store.add_turn(session_id, "assistant", result["final_answer"])

        return result

    # ─── Graph Nodes ──────────────────────────────────────────────────────

    def _classify_query(self, state: AgentState) -> dict:
        """Classify the query as simple_retrieval, multi_step, or clarification.

        Uses the LLM with a classification prompt to determine the query type
        based on the query text and conversation history. Stores the classification
        in response_type for routing: "clarification" for clarification,
        "multi_step" for multi-step, "answer" for simple retrieval.
        """
        history_text = self._format_history(state["conversation_history"])

        prompt = _CLASSIFICATION_PROMPT.format(
            history=history_text or "(no prior conversation)",
            query=state["query"],
        )

        try:
            from langchain_core.messages import HumanMessage

            response = self.llm.invoke([HumanMessage(content=prompt)])
            classification = response.content.strip().lower()

            # Validate classification
            valid_types = {"simple_retrieval", "multi_step", "clarification"}
            if classification not in valid_types:
                logger.warning(
                    f"LLM returned invalid classification '{classification}', "
                    f"defaulting to 'simple_retrieval'"
                )
                classification = "simple_retrieval"

        except Exception as exc:
            logger.error(f"Query classification failed: {exc}, defaulting to simple_retrieval")
            classification = "simple_retrieval"

        # Encode classification into response_type for routing:
        # "clarification" -> clarification path
        # "multi_step" -> decompose path
        # "answer" (default) -> simple retrieval path
        if classification == "clarification":
            response_type = "clarification"
        elif classification == "multi_step":
            response_type = "multi_step"
        else:
            response_type = "answer"

        return {"response_type": response_type}

    def _simple_retrieval(self, state: AgentState) -> dict:
        """Route to RAG chain for simple retrieval and return the answer."""
        try:
            rag_response = self.rag_chain.invoke(state["query"])

            return {
                "final_answer": rag_response.answer,
                "source_attributions": rag_response.source_attributions,
                "retrieval_metadata": rag_response.retrieval_metadata,
                "token_usage": rag_response.token_usage,
                "response_type": "answer",
            }
        except Exception as exc:
            logger.error(f"Simple retrieval failed: {exc}")
            return {
                "final_answer": "An error occurred while processing your request. Please try again later.",
                "response_type": "answer",
            }

    def _decompose_query(self, state: AgentState) -> dict:
        """Decompose the query into max 5 sub-questions."""
        history_text = self._format_history(state["conversation_history"])

        prompt = _DECOMPOSITION_PROMPT.format(
            history=history_text or "(no prior conversation)",
            query=state["query"],
        )

        try:
            from langchain_core.messages import HumanMessage

            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # Parse JSON array of sub-questions
            sub_questions = json.loads(content)

            if not isinstance(sub_questions, list):
                sub_questions = [state["query"]]

            # Ensure all items are strings
            sub_questions = [str(q) for q in sub_questions if q]

            # Cap at 5 sub-questions
            sub_questions = sub_questions[:5]

            if not sub_questions:
                sub_questions = [state["query"]]

        except (json.JSONDecodeError, Exception) as exc:
            logger.warning(f"Query decomposition failed: {exc}, using original query")
            sub_questions = [state["query"]]

        return {
            "sub_questions": sub_questions,
            "step_count": 0,
        }

    def _retrieve_sub_question(self, state: AgentState) -> dict:
        """Retrieve context for the current sub-question via RAG chain.

        Processes one sub-question per invocation, incrementing step_count.
        """
        step_count = state["step_count"]
        sub_questions = state["sub_questions"]
        intermediate_steps = list(state["intermediate_steps"])
        source_attributions = list(state["source_attributions"])
        token_usage = dict(state["token_usage"])
        retrieval_metadata = dict(state["retrieval_metadata"])

        # Check if we've exceeded max steps
        if step_count >= self.MAX_STEPS:
            # Return last intermediate answer with step_limit_reached
            final_answer = intermediate_steps[-1] if intermediate_steps else ""
            return {
                "final_answer": final_answer,
                "step_count": step_count,
                "step_limit_reached": True,
                "response_type": "answer",
            }

        # Get the current sub-question to process
        current_idx = step_count
        if current_idx >= len(sub_questions):
            # All sub-questions processed
            return {
                "step_count": step_count,
                "intermediate_steps": intermediate_steps,
            }

        current_question = sub_questions[current_idx]

        try:
            rag_response = self.rag_chain.invoke(current_question)

            intermediate_steps.append(rag_response.answer)

            # Accumulate source attributions (deduplicate by file_id)
            existing_file_ids = {
                attr.get("file_id") for attr in source_attributions
            }
            for attr in rag_response.source_attributions:
                if attr.get("file_id") not in existing_file_ids:
                    source_attributions.append(attr)
                    existing_file_ids.add(attr.get("file_id"))

            # Accumulate token usage
            if rag_response.token_usage:
                token_usage["prompt_tokens"] = token_usage.get("prompt_tokens", 0) + rag_response.token_usage.get("prompt_tokens", 0)
                token_usage["completion_tokens"] = token_usage.get("completion_tokens", 0) + rag_response.token_usage.get("completion_tokens", 0)
                token_usage["total_tokens"] = token_usage.get("total_tokens", 0) + rag_response.token_usage.get("total_tokens", 0)

            # Update retrieval metadata
            retrieval_metadata = rag_response.retrieval_metadata

        except Exception as exc:
            logger.error(f"Sub-question retrieval failed for '{current_question}': {exc}")
            intermediate_steps.append(f"Unable to retrieve information for: {current_question}")

        return {
            "intermediate_steps": intermediate_steps,
            "source_attributions": source_attributions,
            "token_usage": token_usage,
            "retrieval_metadata": retrieval_metadata,
            "step_count": step_count + 1,
        }

    def _synthesize_answer(self, state: AgentState) -> dict:
        """Synthesize a combined answer from intermediate results."""
        intermediate_steps = state["intermediate_steps"]

        if not intermediate_steps:
            return {
                "final_answer": "I was unable to find relevant information to answer your question.",
                "response_type": "answer",
            }

        # Format intermediate answers
        intermediate_text = "\n\n".join(
            f"Sub-answer {i + 1}: {step}" for i, step in enumerate(intermediate_steps)
        )

        language_instruction = _LANGUAGE_INSTRUCTIONS.get(
            self.language, _LANGUAGE_INSTRUCTIONS["id"]
        )

        prompt = _SYNTHESIS_PROMPT.format(
            query=state["query"],
            intermediate_answers=intermediate_text,
            language_instruction=language_instruction,
        )

        try:
            from langchain_core.messages import HumanMessage

            response = self.llm.invoke([HumanMessage(content=prompt)])
            final_answer = response.content.strip()

            # Accumulate synthesis token usage
            token_usage = dict(state["token_usage"])
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                um = response.usage_metadata
                synthesis_prompt = getattr(um, "input_tokens", 0)
                synthesis_completion = getattr(um, "output_tokens", 0)
                token_usage["prompt_tokens"] = token_usage.get("prompt_tokens", 0) + synthesis_prompt
                token_usage["completion_tokens"] = token_usage.get("completion_tokens", 0) + synthesis_completion
                token_usage["total_tokens"] = token_usage["prompt_tokens"] + token_usage["completion_tokens"]

            return {
                "final_answer": final_answer,
                "response_type": "answer",
                "token_usage": token_usage,
            }

        except Exception as exc:
            logger.error(f"Answer synthesis failed: {exc}")
            # Fall back to concatenating intermediate steps
            fallback = " ".join(intermediate_steps)
            return {
                "final_answer": fallback,
                "response_type": "answer",
            }

    def _generate_clarification(self, state: AgentState) -> dict:
        """Generate a clarifying question for the user."""
        history_text = self._format_history(state["conversation_history"])

        language_instruction = _LANGUAGE_INSTRUCTIONS.get(
            self.language, _LANGUAGE_INSTRUCTIONS["id"]
        )

        prompt = _CLARIFICATION_PROMPT.format(
            history=history_text or "(no prior conversation)",
            query=state["query"],
            language_instruction=language_instruction,
        )

        try:
            from langchain_core.messages import HumanMessage

            response = self.llm.invoke([HumanMessage(content=prompt)])
            clarification = response.content.strip()

        except Exception as exc:
            logger.error(f"Clarification generation failed: {exc}")
            clarification = "Could you please provide more details about what you're looking for?"

        return {
            "final_answer": clarification,
            "response_type": "clarification",
        }

    # ─── Routing Functions ────────────────────────────────────────────────

    def _route_after_classification(self, state: AgentState) -> str:
        """Route to the appropriate node based on query classification.

        Uses the response_type set by _classify_query to determine routing:
        - "clarification" -> generate_clarification
        - "multi_step" -> decompose_query
        - "answer" (or default) -> simple_retrieval

        Returns the node name to route to.
        """
        response_type = state.get("response_type", "answer")

        if response_type == "clarification":
            return "generate_clarification"
        elif response_type == "multi_step":
            return "decompose_query"
        else:
            return "simple_retrieval"

    def _should_continue_reasoning(self, state: AgentState) -> Literal["synthesize", "continue"]:
        """Determine whether to continue retrieving sub-questions or synthesize.

        Checks step_count against MAX_STEPS and whether all sub-questions
        have been processed.
        """
        step_count = state["step_count"]
        sub_questions = state["sub_questions"]

        # If step limit reached, go to synthesis
        if step_count >= self.MAX_STEPS:
            return "synthesize"

        # If all sub-questions have been processed, go to synthesis
        if step_count >= len(sub_questions):
            return "synthesize"

        # Otherwise continue retrieving
        return "continue"

    # ─── Helpers ──────────────────────────────────────────────────────────

    def _format_history(self, history: list[dict[str, str]]) -> str:
        """Format conversation history into a readable string.

        Args:
            history: List of {role, content} dicts.

        Returns:
            Formatted history string, or empty string if no history.
        """
        if not history:
            return ""

        # Limit to MAX_HISTORY_TURNS
        recent_history = history[-self.MAX_HISTORY_TURNS:]

        parts = []
        for turn in recent_history:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            parts.append(f"{role}: {content}")

        return "\n".join(parts)
