"""FocusNavigator is pure logic: exercised on a simulated 3x3 focus grid."""

from __future__ import annotations

import pytest

from streamcart.core.driver.focus import FocusNavigator, Rect
from streamcart.core.driver.protocol import Direction
from streamcart.core.errors import ElementNotInteractableError

CELL = 100.0


class FakeScreen:
    """A grid of focusable cells; the d-pad moves focus one cell, clamped at the edges."""

    def __init__(self, columns: int = 3, rows: int = 3, *, focused: tuple[int, int] | None = (0, 0)) -> None:
        self.columns, self.rows = columns, rows
        self.focused = focused
        self.presses: list[Direction] = []
        self.stuck = False  # simulate a UI that never moves focus

    def rect(self, cell: tuple[int, int]) -> Rect:
        col, row = cell
        return Rect(col * CELL, row * CELL, CELL, CELL)

    def focused_rect(self) -> Rect | None:
        return self.rect(self.focused) if self.focused is not None else None

    def press(self, direction: Direction) -> None:
        self.presses.append(direction)
        if self.stuck:
            return
        if self.focused is None:
            self.focused = (0, 0)
            return
        col, row = self.focused
        col += {Direction.LEFT: -1, Direction.RIGHT: 1}.get(direction, 0)
        row += {Direction.UP: -1, Direction.DOWN: 1}.get(direction, 0)
        self.focused = (min(max(col, 0), self.columns - 1), min(max(row, 0), self.rows - 1))

    def navigator(self, max_moves: int = 20) -> FocusNavigator:
        return FocusNavigator(focused=self.focused_rect, press=self.press, settle=lambda: None, max_moves=max_moves)


def test_moves_diagonally_with_the_minimum_presses() -> None:
    screen = FakeScreen()
    presses = screen.navigator().move_to(lambda: screen.rect((2, 2)))
    assert presses == 4
    assert screen.focused == (2, 2)
    assert sorted(p.value for p in screen.presses) == ["down", "down", "right", "right"]


def test_already_focused_needs_no_presses() -> None:
    screen = FakeScreen(focused=(1, 1))
    assert screen.navigator().move_to(lambda: screen.rect((1, 1))) == 0
    assert screen.presses == []


def test_unfocused_screen_is_nudged_first() -> None:
    screen = FakeScreen(focused=None)
    presses = screen.navigator().move_to(lambda: screen.rect((1, 0)))
    assert screen.presses[0] is Direction.DOWN  # gives the UI focus
    assert screen.focused == (1, 0)
    assert presses == 2


def test_target_that_moves_is_re_read_each_step() -> None:
    screen = FakeScreen()
    positions = iter([(2, 0), (2, 0), (2, 1)])  # the list scrolls while we navigate
    current = [(2, 0)]

    def target() -> Rect:
        current[0] = next(positions, current[0])
        return screen.rect(current[0])

    screen.navigator().move_to(target)
    assert screen.focused == (2, 1)


def test_unreachable_target_fails_with_a_typed_error() -> None:
    screen = FakeScreen()
    screen.stuck = True
    with pytest.raises(ElementNotInteractableError, match="Focus could not reach the target"):
        screen.navigator(max_moves=5).move_to(lambda: screen.rect((2, 2)))
    assert len(screen.presses) <= 10  # one move plus one perpendicular attempt, then it gives up
