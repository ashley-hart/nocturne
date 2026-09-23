# TODO LIST

* GET PLAYER MOVING ON SCREEN, & COLLIDING WITH TILES
* MOVE ON TO FIRST PROTOTYPE LEVEL DESIGN
* Sleep on it so you can figure out what you want with a clear head.
* A clear vision == more effective work. I kinda wanted to get a mechanic 
* or two down and some UI action (even like a score count) up tmw that I 
* can make some graphics for on Sunday.


Note: There is an issue with the timer not beign at the amax limit when the level  starts, i think this has to do with how the menus and the main game loop interact. Implementing a game state manager should resolve this...

    # TODO: Mini Jam 219
    ## MVP
    - make jump/movement feel good [DONE]
    - add score-based win condition (time limit) [DONE] --> needs to communicate with Game class.
    - add roof to tower [DONE]
    - add level parameters height, ruby odds, time limit(level 1, 2, 3 --> local dict for now) [DONE]
    - add level transition (reset/regenerate tilemap + player) [DONE - not polished]

    ## Reliability
    - add generation validation
    - export tilemaps to JSON
    - make sure exported tilemaps are loadable

    ## Polish
    - add art assets
    - add main menu
    - add simple level transition/cutscene if time allows

# Adaptive online level generation

Levels are no longer built all at once when a level starts. Platforms are
generated a few rows above the top of the screen as the player climbs, and
how hard each new jump is depends on how the player has been doing.

```
 player input ─► Telemetry ──summary()──► DifficultyDirector ──target──► OnlineLevelStreamer
 (jumps, landings,   skill rating,          aims for jumps the              asks ChunkGenerator for the
  gems, falls, time) pace, fall rate…        player clears ~75%              next platforms just above the
                                             of the time                     camera ─► Tilemap / Rubies
```

| file | what it does |
| --- | --- |
| `scripts/telemetry.py` | Records jumps, landings, falls, gems and level results, and keeps an Elo-style **skill rating** on the same 0..1 scale as jump difficulty. Saves each session to `telemetry/session_*.json`. |
| `scripts/levelgen.py` | Pure (no pygame) level generator. `JumpModel` replays the Player's jump physics frame by frame to decide what is reachable. `assess_jump` scores a jump's difficulty from the jumps it needs, height margin, landing width and horizontal reach. Six **jump configurations** (staircase, zigzag, leap, chimney, stepping stones, rest) propose platforms, and `ChunkGenerator` keeps the valid one closest to the target difficulty. Gems go on ledges, mid-jump ("arc" gems) or on tempting side branches. |
| `scripts/director.py` | Converts telemetry into a target difficulty: skill, adjusted for pace against the clock, fail streaks and level, with periodic breathers and rate limiting. |
| `scripts/streaming.py` | `OnlineLevelStreamer` keeps the next platform one lookahead above the view, requests a new target for each chunk, keeps enough gems ahead to meet the score goal, and places a reachable exit under the ceiling. |

Guarantees (checked by the tests and the bot playtest):

* every main-path jump is reachable under the real physics, with a safety margin
* nothing spawns inside the view once play starts
* no platform sits in another jump's flight corridor
* the level always contains enough gems for the goal, and the exit is always reachable

In game, **F3** toggles the telemetry panel on the right. `BLOODGEMS_GEN=oneshot python game.py`
runs the original whole-level generator for comparison.

## Tools and tests

```
python -m unittest discover -s tests -t .              # unit + property tests (pure Python)
python tools/preview_level.py --difficulty 0.1 0.5 0.9  # ASCII towers side by side
python tools/bot_playtest.py --levels 20 --skill 0.9    # bot climbs the real game headlessly
python tools/bot_playtest.py --adaptive --true-skill 0.3  # synthetic player; watch skill converge
```
