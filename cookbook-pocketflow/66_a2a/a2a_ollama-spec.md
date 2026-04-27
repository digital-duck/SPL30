**PocketFlow A2A Agent**

The PocketFlow A2A (Agent-to-Agent) agent is a synchronous, non-streaming task manager that runs a PocketFlow agent. The agent accepts tasks with text queries and produces final answers as artifacts.

**Components**

1. **TaskManager**: Responsible for managing tasks, including creating, updating, and deleting tasks.
2. **PocketFlow Agent**: A synchronous, non-streaming task that uses the PocketFlow algorithm to generate responses based on user input.

**Behavior**

1. When a task is received, the TaskManager validates the output modes and updates the task state to WORKING.
2. The TaskManager extracts the text query from the message parts using the `_get_user_query` method.
3. The TaskManager creates an instance of the PocketFlow agent with the extracted query as input.
4. The PocketFlow agent runs synchronously, modifying the shared data dictionary in place.
5. The agent generates a final answer and stores it in the shared data dictionary.
6. The TaskManager packages the final task status and artifact into a SendTaskResponse object.
7. The TaskManager returns the SendTaskResponse object to the client.

**Error Handling**

1. If an error occurs during the execution of the PocketFlow agent, the TaskManager updates the task state to FAILED and returns an InternalError response to the client.
2. If no text query is found in the message parts, the TaskManager returns an InvalidParamsError response to the client.

**Implementation**

The PocketFlow A2A agent implementation consists of three main components:

1. **TaskManager**: Implemented as a subclass of `InMemoryTaskManager`.
2. **PocketFlow Agent**: Implemented using the `create_agent_flow` function from the `flow` module.
3. **Utilities**: Implemented using the `call_llm`, `search_web`, and `server_utils` modules.

**Spec**

The PocketFlow A2A agent specification consists of the following requirements:

1. **Task Validation**: The TaskManager should validate the output modes to ensure compatibility with the SupportedContentTypes.
2. **Query Extraction**: The `_get_user_query` method should extract the first text part from the message parts using a dictionary-based approach.
3. **PocketFlow Agent Execution**: The PocketFlow agent should run synchronously, modifying the shared data dictionary in place.
4. **Final Answer Generation**: The agent should generate a final answer and store it in the shared data dictionary.
5. **Task Status Update**: The TaskManager should update the task state to WORKING before running the PocketFlow agent.
6. **Error Handling**: The TaskManager should handle errors during execution by updating the task state to FAILED and returning an InternalError response to the client.

Note: This specification is based on the provided code snippets and may require additional details or modifications to fully capture the requirements of the PocketFlow A2A agent.