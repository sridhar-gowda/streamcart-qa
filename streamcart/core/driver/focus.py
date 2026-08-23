"""Focus navigation — how ``select()`` works on a television.

TV platforms have no pointer: "select the Checkout button" means *move the
focus indicator onto it with the d-pad, then press OK*. This module holds the
library-agnostic part of that — deciding which direction to press and when to
give up — so Fire TV, Apple TV and Roku adapters share one algorithm and only
supply three primitives: where is focus now, press a direction, let the UI
settle.

Being pure logic it is unit-tested without a device (``tests/framework/test_focus.py``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from streamcart.core.driver.protocol import Direction
from streamcart.core.errors import ElementNotInteractableError


@dataclass(frozen=True)
class Rect:
    """Screen-space bounds of a focusable node."""

    x: float
    y: float
    width: float
    height: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    def contains(self, point: tuple[float, float]) -> bool:
        px, py = point
        return self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height


class FocusNavigator:
    """Drive focus to a target using only directional key presses.

    Parameters are callables so adapters can plug in their own way of reading
    focus (Android's ``active_element``, XCUITest's ``hasFocus``, Roku's
    ``focused="true"`` XML attribute) and pressing keys (Appium keycodes,
    ``mobile: pressButton``, ECP ``/keypress``).
    """

    def __init__(
        self,
        *,
        focused: Callable[[], Rect | None],
        press: Callable[[Direction], None],
        settle: Callable[[], None],
        max_moves: int = 40,
    ) -> None:
        self._focused = focused
        self._press = press
        self._settle = settle
        self._max_moves = max_moves

    def move_to(self, target: Callable[[], Rect]) -> int:
        """Move focus until it lands on ``target``; return the number of presses.

        ``target`` is re-read after every move because lists scroll and
        positions change. Raises ``ElementNotInteractableError`` if focus stops
        moving or the budget runs out — the node is unreachable by d-pad.
        """
        presses = 0
        last_direction: Direction | None = None
        for _ in range(self._max_moves):
            goal = target()
            current = self._focused()
            if current is None:
                # Nothing focused yet (fresh screen): nudge down to give the UI focus.
                direction = Direction.DOWN
            elif goal.contains(current.center) or current.contains(goal.center):
                return presses
            else:
                direction = self._direction(current, goal, avoid=last_direction)
            self._press(direction)
            presses += 1
            self._settle()
            after = self._focused()
            if current is not None and after == current:
                # Focus did not move: either blocked on that axis or at an edge.
                alternative = self._perpendicular(direction, current, goal)
                if alternative is None:
                    break
                self._press(alternative)
                presses += 1
                self._settle()
                if self._focused() == current:
                    break
            last_direction = direction
        raise ElementNotInteractableError(
            f"Focus could not reach the target after {presses} d-pad presses (budget {self._max_moves})"
        )

    @staticmethod
    def _direction(current: Rect, goal: Rect, *, avoid: Direction | None) -> Direction:
        cx, cy = current.center
        gx, gy = goal.center
        dx, dy = gx - cx, gy - cy
        horizontal = Direction.RIGHT if dx > 0 else Direction.LEFT
        vertical = Direction.DOWN if dy > 0 else Direction.UP
        # Larger displacement first; never immediately reverse the last move.
        first, second = (horizontal, vertical) if abs(dx) >= abs(dy) else (vertical, horizontal)
        if avoid is not None and _opposite(first) == avoid:
            return second
        return first

    @staticmethod
    def _perpendicular(direction: Direction, current: Rect, goal: Rect) -> Direction | None:
        cx, cy = current.center
        gx, gy = goal.center
        if direction in (Direction.LEFT, Direction.RIGHT):
            if abs(gy - cy) < 1:
                return None
            return Direction.DOWN if gy > cy else Direction.UP
        if abs(gx - cx) < 1:
            return None
        return Direction.RIGHT if gx > cx else Direction.LEFT


def _opposite(direction: Direction) -> Direction:
    return {
        Direction.UP: Direction.DOWN,
        Direction.DOWN: Direction.UP,
        Direction.LEFT: Direction.RIGHT,
        Direction.RIGHT: Direction.LEFT,
    }[direction]
