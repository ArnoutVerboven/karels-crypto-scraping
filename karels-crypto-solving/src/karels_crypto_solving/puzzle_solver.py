"""Solve a whole Karel's Crypto puzzle with a single agentic chat loop.

Built on the OpenAI Agents SDK. The agent has exactly two tools:

* ``fill_word(word_index, letters)`` - write/erase a (partial) guess; helper
  letters propagate to other words automatically.
* ``check_puzzle()`` - returns whether the whole puzzle is correct.

The puzzle board is injected into the system prompt on every turn via dynamic
instructions, so the agent always sees the latest fill state.
"""

from __future__ import annotations

from dataclasses import dataclass

from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    RunContextWrapper,
    Runner,
    function_tool,
    set_tracing_disabled,
)

from . import config
from .models import Puzzle
from .prompts import PUZZLE_SOLVER_SYSTEM


def render_board(puzzle: Puzzle) -> str:
    """One line per word: index, length, current pattern and the clue."""
    lines = []
    for i, word in enumerate(puzzle.words):
        lines.append(
            f"[{i:>2}] ({word.length:>2}) {puzzle.pattern(i)}  -  {word.cryptogram}"
        )
    return "\n".join(lines)


@function_tool
def fill_word(ctx: RunContextWrapper[Puzzle], word_index: int, letters: str) -> str:
    """Fill word ``word_index`` with ``letters`` (use "_" for unknown/erase)."""
    puzzle = ctx.context
    if not 0 <= word_index < len(puzzle.words):
        return f"Invalid word_index {word_index}; expected 0..{len(puzzle.words) - 1}."
    pattern = puzzle.fill_word(word_index, letters)
    return f"word {word_index} is now '{pattern}'"


@function_tool
def check_puzzle(ctx: RunContextWrapper[Puzzle]) -> bool:
    """Return True when every word is completely and correctly filled."""
    return ctx.context.is_solved()


def _instructions(ctx: RunContextWrapper[Puzzle], agent: Agent[Puzzle]) -> str:
    return PUZZLE_SOLVER_SYSTEM.format(board=render_board(ctx.context))


@dataclass
class PuzzleSolveResult:
    solved: bool
    final_output: str
    puzzle: Puzzle


def build_agent(*, client=None, model: str | None = None) -> Agent[Puzzle]:
    client = client or config.async_openai_client()
    set_tracing_disabled(True)
    return Agent[Puzzle](
        name="Karel's Crypto solver",
        instructions=_instructions,
        tools=[fill_word, check_puzzle],
        model=OpenAIChatCompletionsModel(
            model=model or config.model_name(), openai_client=client
        ),
    )


def solve_puzzle(
    puzzle: Puzzle,
    *,
    client=None,
    model: str | None = None,
    max_turns: int = 60,
) -> PuzzleSolveResult:
    """Run the agentic loop in-place on ``puzzle`` and report the result."""
    agent = build_agent(client=client, model=model)
    result = Runner.run_sync(
        agent,
        "Solve the puzzle. Call check_puzzle when you believe it is complete.",
        context=puzzle,
        max_turns=max_turns,
    )
    return PuzzleSolveResult(
        solved=puzzle.is_solved(),
        final_output=result.final_output or "",
        puzzle=puzzle,
    )
