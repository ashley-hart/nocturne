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