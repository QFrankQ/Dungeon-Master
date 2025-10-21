# Architecture of Multi-Agent Dungeon Master #

There are two agents that dictates the progression of the game: the Gameflow Director & the Dungeon Master. The Gameflow Director (GD) is responsible for managing the game flow and perform context and game state updates. The Dungeon Master (DM) is responsible for performing the game step objectives and generate narration that will be visible to the players at each game step.

## Gameflow Director ##

### Context ###
- **combat arbiter script + System Prompt**: Structured Guidance that describes the phases and steps of the gameflow and gameflow management
- **gameflow directory context (by GD context builder)**
   - **history**: structured chronological summary of history phases/steps/turns, nested turns for actions and reactions are represented in a nested and indented format.
   - **Turn Context**: Context of the current (global) turn, which includes all live messages and nested turn summaries up till present
   - **Current Phase/Step Objectives**: The core objective of the current phase/step as specified by the Flow Director according to the gameflow.
   - **New Messages**: New player message and DM narration

### Responsibility ###

The Gameflow Director (GD) is responsible for managing the game flow based on the combat arbiter script by providing a **step objective** to the Dungeon Master (DM). The context to the GD consists of combat arbiter script (gameflow), history, current turn context, and new message(s). The new message could be either a new DM message or a new player message.

The new DM message usually signals the end of the current step, where the DM successfully accomplished the step objective and no further player input is required. The GD is then responsible for setting the new step objective, signaling game state changes.


### Available function tool calls ###

- **start_and_queue_turns**: Invoked when GD determined that reactions are declared. Queue all reactions in the turn manager (turn stack) so they can be processed sequentially before continue processing the original action. Returns relevant context of the first reaction to be processed.

- **end_turn_and_get_next**: Invoked when GD determines that current turn is complete. Ends current turn, summarizes the current turn, and appends the summary to the parent turns message list. Returns relevant context of the next sibling turn. If no sibling exists, returns relevant context of the parent turn.

### Output: GameflowDirectorResponse class ###
- **new_game_step_objective**: the next step in the combat arbiter script.
- **game_state_update_required** boolean that indicates whether state updates is needed.

## Dungeon Master ##

### Context ###

- **dungeon master prompt (System Prompt)**: Specifies the core directives, rule adjudication protocol, interaction protocol, and basic combat management
- **dungeon master context (by DM context builder)**
   - **history**: structured chronological summary of history phases/steps/turns, nested turns for actions and reactions are represented in a nested and indented format.
   - **Turn Context**: Context of the current (global) turn, which includes all live messages and nested turn summaries up till present
   - **Current Phase/Step Objectives**: The core objective of the current phase/step as specified by the Flow Director according to the gameflow.
   - **New Message**: New message from the players.
   - **Relevant Game State & Rules(Optional)**

### Responsibilities ###

The Dungeon Master (DM) is mainly responsible for adjudicating rules, generate narratives, and interact with the players. It accomplishes the phase/step objective specified by the Gameflow Director(GD) and generates narratives based on the provided context, with the option of retrieving more context from the knowledge base using tool calls and prompting the user for input if further context, clarification is needed. It also judges whether the phase/step objectives are met and signals the GD whether the current step is complete.

### Output: DungeonMasterResponse class ###
- **narrative**: optional game narrative & response to the players.
- **step_complete** boolean that signals the GD about whether the current step is complete
<!-- - **requires_player_input**: boolean that signals the GD whether player input is required -->


## TurnManager ##

### TurnStack ###
The TurnManager keeps a stack of TurnContext for active nested turns/subturns in chronological order. The top turn/subturn in the stack indicates the turn/subturn that the game is currently in.

### TurnContext ###

 - **step_objectives**: the objectives of the current step that the DM should achieve. Specified by the FD.
 - **messages**: list of messages in chronological order. Types of messages include: 
    - ***live messages***: narratives and players DM messages during interaction
    - ***nested summaries***: nested chronological summaries of child turns of the current turn/subturn. Generated and appended to the messages when the child turn is popped from the TurnStack
 - **active character**


## State Extractor ##

### Context ###
Unprocessed live messages of the current turn. Nested summaries are excluded to prevent duplicate state updates.

### responsibility ###
The State Extractor is responsible for extract state updates and return as response immediately (as invoked by the FD) after an action is resolved. It extract updates primarily according to the action resolution narrative supplemented with other player DM interactions in the current turn. Nested summaries of child turns are excluded from the context to prevent duplicate state updates; it is expected that the DM having full context about child turn summaries and be comprehensive when narrating the action resolution of the current turn.

## Turn Summarizer ##

### Context ###
Live messages and the nested summaries of the current turn. 

### responsibility ###
The Turn Summarizer has full context and is expected to summarize and generate the nested summaries for the entire turn/subturn. The nested summaries has the structure of nested action-resolution pairs and should preserve the style and flavor of the original text as it will be part of the context for future FD, DM runs


