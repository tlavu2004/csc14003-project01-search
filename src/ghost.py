"""
This module defines the `Ghost` class, which represents a ghost character in the Pacman game.
The `Ghost` class is responsible for managing the ghost's position, movement, and interaction
with the maze.
It supports pathfinding and movement updates based on a given speed and path dispatcher.

Classes:
    Ghost:
        A subclass of `pygame.sprite.Sprite` and `PathListener` that represents a ghost character
        in the game. It handles movement, pathfinding, and interactions with the maze.
Constants:
    GHOST_TYPES (set): A set of predefined ghost types ("blinky", "clyde", "inky", "pinky").
"""
import os
import random
import pygame as pg

from src.maze import (
   MazeNode, MazeCoord,
   rect_to_maze_coords, find_path_containing_coord, move_along_path, is_snap_within
)
from src.pathfinding import PathListener, PathDispatcher, Pathfinder
from .constant import IMAGES_PATH

GHOST_TYPES = { "blinky", "clyde", "inky", "pinky"}

GHOST_SPRITES_BASE_PATH = os.path.join(IMAGES_PATH, "ghosts")
ghost_sprite_paths = {
    "blinky": os.path.join(GHOST_SPRITES_BASE_PATH, "blinky.png"),
    "clyde": os.path.join(GHOST_SPRITES_BASE_PATH, "clyde.png"),
    "inky": os.path.join(GHOST_SPRITES_BASE_PATH, "inky.png"),
    "pinky": os.path.join(GHOST_SPRITES_BASE_PATH, "pinky.png"),
}

THOUSAND = 1000
ONE_PIXEL = 1

class Ghost(pg.sprite.Sprite, PathListener):
    """
    Represents a ghost character in the Pacman game.
    The Ghost class is responsible for managing the ghost's position, movement,
    and interaction with the maze. It supports pathfinding and movement updates
    based on a given speed and path dispatcher.

    Attributes:
        ghost_type (str): The type of the ghost, chosen from predefined GHOST_TYPES.
        image (pg.Surface): The sprite image of the ghost.
        rect (pg.Rect): The rectangular area representing the ghost's position.
        speed (int): The movement speed of the ghost in pixels per second.
        path (list[MazeNode]): The current path the ghost is following.
        path_dispatcher (PathDispatcher): The dispatcher responsible for handling path requests.
        cumulative_delta_time (int): Accumulated time in milliseconds for movement updates.

    Methods:
        halt_current_and_request_new_path():
            Halts the current path and requests a new path from the path dispatcher.
        update(dt: int):
            Updates the ghost's position based on its speed and the elapsed time (dt).
            Handles path traversal and requests new paths when necessary.
    """

    def __init__(
            self,
            initial_position: MazeCoord,
            speed: int,
            *,
            ghost_type: str | int = None,
            ghost_group: pg.sprite.Group = None,
            path_dispatcher: PathDispatcher = None,
            path_finder: Pathfinder = None,
            ):
        if ghost_group is None:
            pg.sprite.Sprite.__init__(self)
        else:
            # Add the ghost to the provided group
            pg.sprite.Sprite.__init__(self, ghost_group)
        self.group = ghost_group

        # Deal with ghost type
        if ghost_type is None:
            ghost_type = random.choice(list(GHOST_TYPES))
        elif isinstance(ghost_type, int):
            ghost_type = list(GHOST_TYPES)[ghost_type % len(GHOST_TYPES)]
        elif ghost_type not in GHOST_TYPES:
            raise ValueError(f"Invalid ghost type: {ghost_type}. Must be one of {GHOST_TYPES}.")
        self.image = pg.image.load(ghost_sprite_paths[ghost_type]).convert()
        self.ghost_type = ghost_type

        _initial_position = initial_position.rect.topleft
        self.rect = self.image.get_rect().move(_initial_position)
        self.speed = speed # in pixels per second

        # Path related attributes
        self.path: list[MazeNode] = []
        self.path_dispatcher = path_dispatcher
        self.path_finder = path_finder
        if path_dispatcher is not None:
            path_dispatcher.register_listener(self)
            _initial_path = find_path_containing_coord(
                rect_to_maze_coords(initial_position.rect),
                path_dispatcher.maze_layout.maze_dict,
                path_dispatcher.maze_layout.maze_shape()
            )
            if _initial_path is None:
                raise ValueError(
                    f"Invalid initial path for ghost at initial position {initial_position}."
                    )
            # Invariant: self.path should never be empty,
            # and should always contain at least one node, in this case it's waiting in a place.
            self.path = list(
                _initial_path if _initial_path[1] is not None else (_initial_path[0],)
                )

        # Cumulative delta time for movement update
        self.cumulative_delta_time = 0 # in milliseconds

    def halt_current_and_request_new_path(self):
        if len(self.path) == 0:
            print("Warning: Ghost has no path to follow.")
            if not self.path_dispatcher:
                print("-------: No path dispatcher available.")
                return
            print("-------: Temporarily calculating a new path.")
            current_path = find_path_containing_coord(
                rect_to_maze_coords(self.rect),
                self.path_dispatcher.maze_layout.maze_dict,
                self.path_dispatcher.maze_layout.maze_shape()
            )
            if current_path is None:
                print("-------: Fatal error - ghost is not currently in a path.")
                return
            self.path = list(
                current_path if current_path[1] is not None else (current_path[0],)
            )
        elif is_snap_within(self.rect.center, self.path[0]):
            self.path = self.path[:1] # Keep the first node in the path
        else:
            self.path = self.path[:2] # Keep the first two nodes in the path

        # Guard for the case self.path length is 1
        self.waiting_for_path = True
        self.path_dispatcher.receive_request_for(
            listener=self,
            start_location=(self.path[0], self.path[1] if len(self.path) > 1 else None),
            forced_request=True,
            )

    def update(self, dt: int) -> None:
        """
        Update the ghost's position based on its speed and direction.

        Time delta is in milliseconds. Speed is pixels per second.
        """
        if self.is_waiting_for_path_conflict_resolution():
            return
        if self.new_path:
            self.path = self.new_path
            self.new_path = []
        if not self.path or len(self.path) == 0:
            print("Warning: Ghost has no path to follow.")
            return
        if len(self.path) == 1:
            if self.waiting_for_path:
                return
            if not is_snap_within(self.rect.center, self.path[0]):
                current_location = find_path_containing_coord(
                    rect_to_maze_coords(self.rect),
                    self.path_dispatcher.maze_layout.maze_dict,
                    self.path_dispatcher.maze_layout.maze_shape()
                )
                if current_location is None:
                    print("Warning: Ghost is not currently in a path.")
                    return
                self.path_dispatcher.receive_request_for(
                    listener=self,
                    start_location=current_location,
                    )
                return
            self.path_dispatcher.receive_request_for(
                listener=self,
                start_location=(self.path[0], None),
                )
            return
        if self.path:
            previous_cumulative_delta_time = self.cumulative_delta_time

            _moving_distance: int
            if dt * self.speed // THOUSAND >= ONE_PIXEL:
                _moving_distance = dt * self.speed // THOUSAND
                # Cumulate the remainder part of the distance
                self.cumulative_delta_time += dt - _moving_distance * THOUSAND // self.speed
                if self.cumulative_delta_time * self.speed // THOUSAND >= ONE_PIXEL:
                    _moving_distance += self.cumulative_delta_time * self.speed // THOUSAND
                    self.cumulative_delta_time = 0
            else:
                # Less-than-1-pixel-per-second fix
                self.cumulative_delta_time += dt
                if self.cumulative_delta_time * self.speed // THOUSAND < ONE_PIXEL:
                    return
                _moving_distance = self.cumulative_delta_time * self.speed // THOUSAND
                self.cumulative_delta_time = 0

            # XXX: Teleporting to the new position, bypassing other guys if frame rate is too low
            #      Just a reminder, should not be a big deal
            new_path, new_center = move_along_path(
                self.rect.center,
                self.path,
                max(_moving_distance, 1)
                )

            # Check for collisions with other sprites
            checking_rect = pg.Rect(self.rect)
            checking_rect.center = new_center
            colliding_sprites = sprites_collided_with_rect(checking_rect, self.group)
            other_colliding_sprites = [sprite for sprite in colliding_sprites if sprite is not self]
            if other_colliding_sprites:
                # Collision detected, revert to the previous state
                self.cumulative_delta_time = previous_cumulative_delta_time

                # Dispatch a path conflict resolution event
                self.path_dispatcher.handle_path_conflict_between(
                    self,
                    other_colliding_sprites[0],
                )
                return
            # Update the ghost's position and path
            self.path = new_path
            self.rect.center = new_center

def sprites_collided_with_rect(
        rect: pg.Rect,
        group: pg.sprite.Group = None
    ) -> list[pg.sprite.Sprite]:
    """
    Check if the given rectangle collides with any sprite in the specified group.

    If the group is None, it returns an empty list.

    Args:
        rect (pg.Rect): The rectangle to check for collisions.
        group (pg.sprite.Group, optional): The group of sprites to check against. Defaults to None.
    
    Returns:
        list[pg.sprite.Sprite]: A list of sprites from the group that collide with the rectangle.
    """
    if group is None:
        return []
    return rect.collideobjectsall(group.sprites())
