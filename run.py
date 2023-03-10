"""
    Snake game using curses for graphics and input
"""

import curses
import enum
import random
import time
from typing import List, Tuple, Dict
from dataclasses import dataclass


# +----------------------------------------------------+
# |                     CONSTANTS                      |
# +----------------------------------------------------+


FPS = 30
GAME_WIDTH = 15
GAME_HEIGHT = 10
MAX_SCORE = GAME_WIDTH * GAME_HEIGHT - 1
SNAKE_MOVE_DELAY = 5
BORDER_CHARS = ("|", "|", "-", "-", "+", "+", "+", "+")
MESSAGES = [
    "NICE TRY!",
    "GOOD JOB!",
    "WELL DONE!",
    "CONGRATULATIONS!",
    "PERFECT!"
]


# +----------------------------------------------------+
# |                  UTILITY CLASSES                   |
# +----------------------------------------------------+


class Direction(enum.IntEnum):
    """
        Enum for the directions the snake can travel
    """

    # opposite inputs add to 3
    UP = 0
    RIGHT = 1
    LEFT = 2
    DOWN = 3
    NONE = -1


class Colors(enum.IntEnum):
    """
        Enum for color indices to be used when drawing
    """

    TEXT = 1
    SNAKE = 2
    APPLE = 3


@dataclass
class Point:
    """
        A 2D position in the game
    """
    x: int
    y: int

    def copy(self) -> "Point":
        """
            Returns a shallow copy of this point
        """

        return Point(self.x, self.y)


class Segment:
    """
        A segment of the snake's body
    """

    def __init__(self, pos: Point):
        self.pos = pos

    def __eq__(self, other):
        return self.pos == other.pos

    def draw(self, window):
        """
            Draw the segment to the screen
        """

        window.draw_square(self.pos, Colors.SNAKE)


# +----------------------------------------------------+
# |                      WINDOWS                       |
# +----------------------------------------------------+


class Window:
    """
        Thin wrapper around `curses._CursesWindow`
    """

    def __init__(
            self,
            screen,
            height: int,
            width: int,
            y: int,
            x: int,
            *,
            has_border: bool = True):
        self.win = screen.subwin(height, width, y, x)
        self.has_border = has_border

    def clear(self):
        """
            Clear the window, redrawing its border if it has one
        """

        self.win.erase()
        if self.has_border:
            self.win.border(*BORDER_CHARS)

    def refresh(self):
        """
            Refresh the window
        """

        self.win.refresh()

    def write(self, pos: Tuple[int, int], text: str):
        """
            Write `text` in the window at position `pos`
        """

        self.win.attron(curses.color_pair(Colors.TEXT))
        self.win.addstr(*pos, text)
        self.win.attroff(curses.color_pair(Colors.TEXT))

    def draw_square(self, pos: Point, color: Colors):
        """
            Draw a square in `window` at `pos` with `color`
        """

        self.win.attron(curses.color_pair(color))
        self.win.addstr(pos.y + 1, pos.x * 2 + 1, "  ")
        self.win.attroff(curses.color_pair(color))

    @property
    def size(self) -> Tuple[int, int]:
        """
            The size (w, h) of the window
        """

        y, x = self.win.getmaxyx()
        return (x, y)


class GameWindow(Window):
    """
        The game window. Contains the snake and the apple
    """

    def __init__(self, screen):
        screen_height, screen_width = screen.getmaxyx()

        height = GAME_HEIGHT + 2
        width = GAME_WIDTH * 2 + 2
        y = screen_height // 2 - GAME_HEIGHT // 2
        x = screen_width // 2 - GAME_WIDTH - 6

        super().__init__(screen, height, width, y, x)

    def draw(self, snake: "Snake", apple: "Apple"):
        """
            Draw the game window (the snake and the apple)
        """

        self.clear()

        snake.draw(self)
        apple.draw(self)

        self.refresh()


class ScoreWindow(Window):
    """
        The score window. Contains the title and the score counter
    """

    def __init__(self, screen):
        screen_height, screen_width = screen.getmaxyx()

        height = 3
        width = GAME_WIDTH * 2 + 2
        y = screen_height // 2 - GAME_HEIGHT // 2 - 2
        x = screen_width // 2 - GAME_WIDTH - 6

        super().__init__(screen, height, width, y, x)

    def draw(self, score: int):
        """
            Write the player's score in the score subwindow

            Example:
            +--------------------+
            |  SCORE   |   13    |
            +--------------------+
        """

        self.clear()

        (x, _y) = self.size
        center = x // 2

        # write the word "SCORE" in the left half, center aligned
        self.write((1, 1), f"{'SCORE': ^{center - 1}}")

        # write a pipe character in the middle as a separator
        self.write((1, center), "|")

        # write the score in the right half, center aligned
        self.write((1, center + 1), f"{score: ^{center - 2}}")

        self.refresh()


class HighScoreWindow(Window):
    """
        The high score window. Contains the player's high scores
    """

    def __init__(self, screen):
        screen_height, screen_width = screen.getmaxyx()

        height = GAME_HEIGHT + 4
        width = 13
        y = screen_height // 2 - GAME_HEIGHT // 2 - 2
        x = screen_width // 2 + GAME_WIDTH - 3

        super().__init__(screen, height, width, y, x)

    def draw(self, scores: List[int]):
        """
            Write the player's high scores in the high score window
            to the right of the game window
        """

        self.clear()

        (x, y) = self.size

        # write the word "HISCORE" at the top, center aligned
        self.write((1, 2), f"{'HISCORE': ^{x - 3}}")

        # write a separator below the window title
        self.write((2, 0), "+----+------+")

        high_scores = sorted(scores, reverse=True)

        # iterate over as many high scores as will fit in the window
        for i in range(y - 4):
            if i < len(high_scores):
                score = high_scores[i]
                rank = i + 1
            else:
                score = ""
                rank = ""

            row = i + 3

            # write the rank and score in the corresponding row
            self.write((row, 1), f" {rank: >2} | {score: >4} ")

        self.refresh()


class MessageWindow(Window):
    """
        The message window. Contains the finish message and controls
    """

    def __init__(self, screen):
        screen_height, screen_width = screen.getmaxyx()

        height = 1
        width = GAME_WIDTH * 2 + 12
        y = screen_height // 2 + GAME_HEIGHT // 2 + 3
        x = screen_width // 2 - GAME_WIDTH - 4

        super().__init__(screen, height, width, y, x, has_border=False)

    def draw(self, is_dead: bool, score: int):
        """
            Write the finish message and the controls to the window
        """

        self.clear()

        (x, _y) = self.size

        if is_dead:
            message = get_finish_message(score)
            self.write((0, 0), f"{message} R = RETRY")

        self.write((0, x - 9), "Q = QUIT")

        self.refresh()


# +----------------------------------------------------+
# |                    MAIN CLASSES                    |
# +----------------------------------------------------+


class Game:
    """
        The whole game state. Controls the gameplay, graphics, etc.
    """

    def __init__(self, screen):
        self.screen = screen

        game_win = GameWindow(screen)
        score_win = ScoreWindow(screen)
        hiscore_win = HighScoreWindow(screen)
        message_win = MessageWindow(screen)

        self.windows: Dict[str, Window] = {
            "game": game_win,
            "score": score_win,
            "hiscore": hiscore_win,
            "message": message_win
        }

        self.snake = Snake()
        self.apple = Apple(self.snake)

        # the player's current score this game
        self.score = 0

        # all of the player's scores since they started playing
        self.scores: List[int] = []

        # a queue of inputs to be applied to the snake
        self.inputs: List[Direction] = []

    def handle_input(self) -> bool:
        """
            Handle the player's input, adding a direction to the
            input queue if necessary.
            Returns False if the player quits the game.
        """

        k = self.screen.getch()

        # if the player presses q, close the game
        if k == ord("q"):
            return False

        if k == ord("r") and self.snake.is_dead():
            self.snake.reset()
            self.apple.set_new_pos(self.snake)
            self.score = 0
            self.inputs = []

        # add the player input direction to the input queue
        if k == curses.KEY_UP:
            self.inputs.append(Direction.UP)
        elif k == curses.KEY_DOWN:
            self.inputs.append(Direction.DOWN)
        elif k == curses.KEY_LEFT:
            self.inputs.append(Direction.LEFT)
        elif k == curses.KEY_RIGHT:
            self.inputs.append(Direction.RIGHT)

        return True

    def draw(self):
        """
            Update the game's graphics.
            Calls each window's `draw` method
        """

        self.screen.erase()

        self.windows["game"].draw(self.snake, self.apple)
        self.windows["score"].draw(self.score)
        self.windows["hiscore"].draw(self.scores)
        self.windows["message"].draw(self.snake.is_dead(), self.score)

        self.screen.refresh()

    def update(self):
        """
            Update the game's state
        """

        # update the snake
        self.snake.update(self.inputs)

        # if the snake's head coincides with the apple, it eats it
        if not self.snake.is_dead() and self.snake.head.pos == self.apple.pos:
            # move the apple to a new position
            self.apple.set_new_pos(self.snake)

            # increase the snake's length by one segment
            self.snake.add_segment(self.snake.head)
            self.score += 1

        # the program would hang forever if the player collected
        # `MAX_SCORE` apples, specifically in the `while` loop in
        # `Apple.set_new_pos`, as every possible position would overlap
        # with the snake. thus we need to manually set the snake to
        # dead so that the player can actually win.
        if self.score == MAX_SCORE:
            self.snake.change_state(self.snake.State.DEAD)

        # if the snake has just died, add the current score
        # to the player's `scores` list
        if self.snake.is_dead() and self.snake.counter == 1:
            self.scores.append(self.score)


class Snake:
    """
        The snake that the player controls using the arrow keys
    """

    class State(enum.IntEnum):
        """
            The snake's current state
            WAIT: The snake is waiting to move
            MOVE: The snake is moving based on the player input
            DEAD: The snake is dead after hitting itself/a wall
        """

        WAIT = 0
        MOVE = 1
        DEAD = 2

    def __init__(self):
        self.head = Segment(Point(GAME_WIDTH // 2, GAME_HEIGHT // 2))
        self.body_segments: List[Segment] = [self.head]
        self.state: self.State = self.State.WAIT
        self.counter = 0

        # leave the snake stationary at the start
        self.prev_input: Direction = Direction.NONE
        self.cur_input: Direction = Direction.NONE

    def reset(self):
        """
            Reset the snake's state, position and body
        """

        self.head.pos = Point(GAME_WIDTH // 2, GAME_HEIGHT // 2)
        self.body_segments: List[Segment] = [self.head]
        self.prev_input = Direction.NONE
        self.cur_input = Direction.NONE

        self.change_state(self.State.WAIT)

    def change_state(self, state: State):
        """
            Change the snake's state and reset the frame counter
        """

        self.state = state
        self.counter = 0

    def update_wait(self):
        """
            Update the snake when it's in the WAIT state.
            Waits for `SNAKE_MOVE_DELAY` frames and then enters the MOVE state
        """

        if self.counter == SNAKE_MOVE_DELAY:
            self.change_state(self.State.MOVE)

    def update_move(self, inputs: List[Direction]):
        """
            Update the snake when it's in the MOVE state.
            Moves based on the player's input.
            Enters the DEAD state if this move made the snake die.
            Enters the WAIT state otherwise.
        """

        # if the player didn't input anything, continue moving in the
        # same direction
        self.cur_input = None
        if len(inputs) == 0:
            self.cur_input = self.prev_input
        else:
            self.cur_input = inputs.pop(0)

        # don't change direction if the snake would turn back on itself
        if self.cur_input + self.prev_input == 3:
            self.cur_input = self.prev_input

        # apply the movement direction to the snake
        is_dead = self.move(self.cur_input)
        self.prev_input = self.cur_input

        if is_dead:
            self.change_state(self.State.DEAD)
        else:
            self.change_state(self.State.WAIT)

    def update(self, inputs):
        """
            Update the snake once per frame.
            Increment the `counter` attribute.
            Calls the `update_*` method corresponding to the snake's state.
        """

        self.counter += 1

        if self.state == self.State.WAIT:
            self.update_wait()

        elif self.state == self.State.MOVE:
            self.update_move(inputs)

        elif self.state == self.State.DEAD:
            pass

    def move(self, direction: Direction) -> bool:
        """
            Move the snake's head in a direction, and have its body follow it.
            Returns True if the snake dies, otherwise returns False
        """

        prev_head = self.head.pos.copy()

        # move head based on direction passed in
        if direction == Direction.UP:
            self.head.pos.y -= 1
        elif direction == Direction.DOWN:
            self.head.pos.y += 1
        elif direction == Direction.LEFT:
            self.head.pos.x -= 1
        elif direction == Direction.RIGHT:
            self.head.pos.x += 1

        # clamp snake position to stay within the game window
        self.head.pos.x = clamp(self.head.pos.x, 0, GAME_WIDTH - 1)
        self.head.pos.y = clamp(self.head.pos.y, 0, GAME_HEIGHT - 1)

        # the snake dies if it hits a wall (if the above clamps succeed)
        if self.head.pos == prev_head and direction != Direction.NONE:
            return True

        # the snake dies if it crashes into itself
        if self.head in self.body_segments[1:-1]:
            return True

        # body follows after head by moving the last segment to the head's
        # position on the previous frame
        if len(self.body_segments) > 1:
            tail = self.body_segments.pop()
            tail.pos.x = prev_head.x
            tail.pos.y = prev_head.y
            self.body_segments.insert(1, tail)

        return False

    def draw(self, window):
        """
            Draw the snake to the game window
        """

        self.head.draw(window)
        for segment in self.body_segments:
            segment.draw(window)

    def add_segment(self, segment: Segment):
        """
            Add a segment to the snake's body
        """

        pos = segment.pos.copy()
        self.body_segments.append(Segment(pos))

    def check_overlap(self, pos: Point) -> bool:
        """
            Check if a point `pos` overlaps with the snake's body
        """

        for segment in self.body_segments:
            if segment.pos == pos:
                return True

        return False

    def is_dead(self) -> bool:
        """
            Returns True if the snake is dead, and False if not
        """

        return self.state == self.State.DEAD


class Apple:
    """
        Apple that the snake can eat to make its body longer
    """

    def __init__(self, snake: Snake):
        self.set_new_pos(snake)

    def set_new_pos(self, snake: Snake):
        """
            Place the apple in a new random position that doesn't
            overlap with the snake
        """
        self.pos = Point(
            random.randrange(0, GAME_WIDTH),
            random.randrange(0, GAME_HEIGHT)
        )

        # ensure the apple doesn't overlap the snake
        while snake.check_overlap(self.pos):
            self.pos = Point(
                random.randrange(0, GAME_WIDTH),
                random.randrange(0, GAME_HEIGHT)
            )

    def draw(self, window):
        """
            Draw the apple to the game window
        """

        window.draw_square(self.pos, Colors.APPLE)


# +----------------------------------------------------+
# |                 UTILITY FUNCTIONS                  |
# +----------------------------------------------------+


def clamp(num: int, lower: int, upper: int) -> int:
    """
        Returns `num` clamped between `lower` and `upper`
    """

    if num > upper:
        return upper

    if num < lower:
        return lower

    return num


def get_finish_message(score) -> str:
    """
        Returns the message to be presented to the player when
        the snake dies, based on their score.
    """

    percentage = score / MAX_SCORE
    if percentage < 0.1:
        return MESSAGES[0]
    if percentage < 0.2:
        return MESSAGES[1]
    if percentage < 0.5:
        return MESSAGES[2]
    if percentage != MAX_SCORE:
        return MESSAGES[3]

    return MESSAGES[4]


# +----------------------------------------------------+
# |                PROGRAM ENTRYPOINT                  |
# +----------------------------------------------------+


def main(screen):
    """
        Main program entrypoint
    """

    # initialize the screen
    screen.erase()
    screen.refresh()

    # make `getch` non-blocking
    screen.nodelay(1)

    # try to turn off the cursor
    try:
        curses.curs_set(0)
        supports_invisible_cursor = True
    except curses.error:
        supports_invisible_cursor = False

    # initialize colors used for the game
    curses.init_pair(Colors.TEXT, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(Colors.SNAKE, curses.COLOR_GREEN, curses.COLOR_GREEN)
    curses.init_pair(Colors.APPLE, curses.COLOR_RED, curses.COLOR_RED)

    game = Game(screen)

    try:
        # main game loop
        running = True
        while running:
            frame_start = time.time()

            # read the player input
            running = game.handle_input()

            game.update()
            game.draw()

            # limit framerate to `FPS`
            frame_end = time.time()
            frame_delta = frame_end - frame_start
            if frame_delta < 1 / FPS:
                time.sleep(1 / FPS - frame_delta)

    finally:
        # turn the cursor back on after the game ends
        if supports_invisible_cursor:
            curses.curs_set(1)


if __name__ == "__main__":
    curses.wrapper(main)
