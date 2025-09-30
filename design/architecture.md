# Architecture of Multi-Agent Dungeon Master#

There are two main agents that dictates the progression of the game: the Flow Director & the Dungeon Master. The Flow Director (FD) is responsible for managing the game flow and perform mechanical and game state updates. The Dungeon Master (DM) is responsible for performing the objectives and generate narration that will be visible to the players at each game step.

## Flow Director ##

### Context ###
- **combat arbiter script (System Prompt)**: Structured Guidance that describes the phases and steps of the gameflow
- **history**: structured chronological summary of history phases/steps/turns, nested turns for actions and reactions are represented in a nested and indented format.
- **Turn Context**: Context of the current (global) turn, which includes all live messages and nested turn summaries up till present
- **New Message**: New message from either players or the Dungeon Master.

### Responsibility ###

The Flow Director (FD) is responsible for managing the game flow based on the combat arbiter script by providing a *step objective* to the Dungeon Master (DM). It is also partially responsible for identifying relevant post-run context retrieval that should be provided in the context to the DM. The context to the FD consists of combat arbiter script (gameflow), history, current turn context, and new message(s). The new message could be either a new DM message or a new player message. 

The new player message ideally responds to the prompt provided by the DM. Usually the FD simply identifies the relevant post-run context retrieval tool-calls without much additional action.

The new DM message usually signals the end of the current step, where the DM successfully accomplished the step objective and no further player input is required. The FD is then responsible to perform mechanical updates based on the current step, advancing a step, and identify post-run context retrieval tool-calls. This is how the system make progress according to the gameflow in the system prompt when player input is not required by the DM.  

### Available Post-run & In-run Tool-calls ###

- **retrieve_state**: This should be a generic function that will allow full or partial retrieval of character states. For example, retrieving the entire character state of a list of characters, or retrieving only conditions and spells of a specific character.
- **retrieve_rules**: This should retrieve relevant rules to a list of queries from the rulebook vector store.

- **start_turn**: Starts a new turn/subturn in combat, which pushes a new TurnContext onto the TurnStack in the TurnManager. 

- **end_turn**: Ends a turn/subturn in combat, which calls **Turn Summarizer** to summarize the TurnContext into a nested turn summary, append the summary to the parent TurnContext, and pop the current TurnContext from the TurnStack.

- **advance_step**: advances a step by updating the step objectives in the current TurnContext

- **resolve_action**: resolves an action by calling the **state extractor** to perform game state updates for the current turn/subturn using its live messages as context

## Dungeon Master##

### Context###

- **dungeon master prompt (System Prompt)**: Specifies the core directives, rule adjudication protocol, interaction protocol, and basic combat management
- **history**: structured chronological summary of history phases/steps/turns, nested turns for actions and reactions are represented in a nested and indented format.
- **Turn Context**: Context of the current (global) turn, which includes all live messages and nested turn summaries up till present
- **Phase/Step Objectives**: The core objective of the current phase/step as specified by the Flow Director according to the gameflow.
- **New Message**: New message from the players.

### Responsibilities ###

The Dungeon Master (DM) is mainly responsible for adjudicating rules, generate narratives, and interact with the players. It accomplishes the phase/step objective specified by the Flow Director(FD) and generates narratives based on the provided context, with the option of retrieving more context from the knowledge base using tool calls and prompting the user for input if further context, clarification is needed. It also judges whether the phase/step objectives are met and signals the FD whether the current step is complete.

### Output ###
- **narrative**: optional narrative that progresses the story of the game.
- **player_prompt**: optional prompt to the player for asking/answering questions, clarifications, and context
- **step_complete** boolean that signals the FD about whether the current step is complete
- **requires_player_input**: boolean that signals the FD whether player input is required


## TurnManager ##

### TurnStack ###
The TurnManager keeps a stack of TurnContext for active nested turns/subturns in chronological order. The top turn/subturn in the stack indicates the turn/subturn that the game is currently in.

### TurnContext ###

 - **step_objectives**: the objectives of the current step that the DM should achieve. Specified by the FD.
 - **messages**: list of messages in chronological order. Types of messages include: 
    - ***live messages***: narratives and players DM messages during interaction
    - ***nested summaries***: nested chronological summaries of child turns of the current turn/subturn. Generated and appended to the messages when the child turn is popped from the TurnStack
 - **active characters**
 - **initiative order**


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


