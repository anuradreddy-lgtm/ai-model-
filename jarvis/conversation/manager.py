"""Conversation Manager orchestrating dialog state, history, and tools."""

import json
import re
from typing import Callable, Dict, List, Optional, Tuple
from jarvis.config import config
from jarvis.core.events import bus
from jarvis.core.state import AssistantState
from jarvis.llm.ollama_client import OllamaClient, OllamaError
from jarvis.llm.prompts import build_tool_prompt, SYSTEM_PROMPT
from jarvis.storage.memory import memory_manager
from jarvis.utils.logger import logger
from datetime import datetime


class ConversationManager:
    """Manages active chat session, memory bounds, and message flow."""

    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.ollama = ollama_client or OllamaClient()
        self.history: List[Dict[str, str]] = []
        self.session_id: str = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        try:
            from jarvis.tools import registry
            self._tool_descriptions = registry.get_descriptions()
        except ImportError:
            self._tool_descriptions = "No external tools registered yet."
        self._current_state = AssistantState.SLEEPING

    def set_state(self, new_state: AssistantState) -> None:
        """Update current assistant state and broadcast via event bus."""
        if self._current_state != new_state:
            self._current_state = new_state
            logger.info(f"State transition: {new_state.name}")
            bus.state_changed.emit(new_state)

    @property
    def current_state(self) -> AssistantState:
        return self._current_state

    def update_tool_descriptions(self, desc: str) -> None:
        """Update tool descriptions exposed in system prompt."""
        self._tool_descriptions = desc

    def get_system_prompt(self) -> str:
        """Build complete system prompt with active tools and user memories."""
        base_prompt = build_tool_prompt(self._tool_descriptions) if self._tool_descriptions else SYSTEM_PROMPT
        memories = memory_manager.format_memories_for_prompt()
        if memories:
            return f"{base_prompt}\n\n{memories}"
        return base_prompt

    def reset_conversation(self) -> None:
        """Clear active in-memory conversation and generate a new session."""
        self.history.clear()
        self.session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        logger.info("Conversation history reset.")

    def add_message(self, role: str, content: str) -> None:
        """Append message to context, persist to SQLite, and enforce max history bounds."""
        self.history.append({"role": role, "content": content})
        memory_manager.save_message(self.session_id, role, content)

        # Keep context within configured turn limit (preserving pairs of user/assistant)
        max_turns = config.ollama.max_context_turns
        if len(self.history) > max_turns * 2:
            # Trim from beginning
            excess = len(self.history) - (max_turns * 2)
            self.history = self.history[excess:]
            logger.debug(f"Trimmed {excess} old conversation turns to preserve context window.")

    def build_payload_messages(self) -> List[Dict[str, str]]:
        """Construct the full message list for Ollama including system prompt."""
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        messages.extend(self.history)
        return messages

    def parse_action_block(self, text: str) -> Optional[Tuple[str, dict]]:
        """Extract tool call `ACTION: {"tool": "...", "args": {...}}` if present."""
        action_idx = text.find("ACTION:")
        if action_idx == -1:
            return None

        # Find the first opening brace after ACTION:
        start_idx = text.find("{", action_idx)
        if start_idx == -1:
            return None

        # Trace balanced braces
        depth = 0
        in_string = False
        escape = False
        end_idx = -1

        for i in range(start_idx, len(text)):
            char = text[i]

            if escape:
                escape = False
                continue

            if char == "\\":
                escape = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if not in_string:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        end_idx = i + 1
                        break

        if end_idx == -1:
            return None

        json_str = text[start_idx:end_idx].strip()
        try:
            data = json.loads(json_str)
            tool_name = data.get("tool")
            tool_args = data.get("args", {})
            if tool_name:
                return str(tool_name), dict(tool_args)
        except Exception as exc:
            logger.warning(f"Failed to parse action JSON '{json_str}': {exc}")

        return None

    def clean_final_response(self, text: str) -> str:
        """Strip any internal action blocks, JSON schema, or system tags to leave ONLY the final response."""
        cleaned = text
        action_match = self.parse_action_block(text)
        if action_match:
            action_idx = cleaned.find("ACTION:")
            if action_idx != -1:
                brace_end = cleaned.find("}", action_idx)
                while brace_end != -1 and brace_end + 1 < len(cleaned) and cleaned[brace_end + 1] == "}":
                    brace_end += 1
                if brace_end != -1:
                    cleaned = cleaned[:action_idx] + cleaned[brace_end + 1:]
                else:
                    cleaned = cleaned[:action_idx]

        cleaned = re.sub(r"```(?:json)?\s*ACTION:.*?```", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"ACTION:\s*\{.*?\}", "", cleaned, flags=re.DOTALL)
        cleaned = cleaned.strip()
        return cleaned or text.strip()

    def process_user_input(
        self,
        user_text: str,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Process incoming user message, query local LLM, and return reply."""
        clean_text = user_text.strip()
        if not clean_text:
            return ""

        # Update state to THINKING
        self.set_state(AssistantState.THINKING)
        self.add_message("user", clean_text)
        bus.message_received.emit("user", clean_text)

        try:
            # Ensure model is valid before streaming
            try:
                self.ollama.ensure_model_available()
            except OllamaUnavailableError:
                self.set_state(AssistantState.ERROR)
                error_msg = f"Cannot reach local Ollama daemon at {self.ollama.base_url}. Please ensure Ollama is running."
                logger.error(error_msg)
                bus.generation_error.emit(error_msg)
                return error_msg
            except ModelNotFoundError:
                self.set_state(AssistantState.ERROR)
                error_msg = f"Model '{self.ollama.model}' is not installed in Ollama. Please run 'ollama pull {self.ollama.model}'."
                logger.error(error_msg)
                bus.generation_error.emit(error_msg)
                return error_msg

            messages = self.build_payload_messages()

            # Smart streaming interceptor:
            # Buffer initial tokens to detect if model is invoking a tool action.
            # If not an action, stream immediately to on_token for instant ~130ms TTFT.
            buffered_tokens: List[str] = []
            streaming_started = False
            has_action = False

            def token_filter(token: str) -> None:
                nonlocal streaming_started, has_action
                if not on_token:
                    return

                if streaming_started:
                    on_token(token)
                    return

                buffered_tokens.append(token)
                accumulated = "".join(buffered_tokens)

                if "ACTION:" in accumulated or "```" in accumulated:
                    has_action = True
                    return

                if len(accumulated) >= 12 or "\n" in accumulated:
                    streaming_started = True
                    for tok in buffered_tokens:
                        on_token(tok)

            raw_reply = self.ollama.chat_stream(
                messages=messages,
                on_token=token_filter,
            )

            if not raw_reply:
                raw_reply = "I did not receive a response from the model."

            # Flush any short unstreamed direct response
            if not streaming_started and not has_action and on_token and buffered_tokens:
                for tok in buffered_tokens:
                    on_token(tok)

            # Check if model requested a tool execution
            action = self.parse_action_block(raw_reply)
            if action:
                tool_name, tool_args = action
                logger.info(f"Model triggered tool: {tool_name} with args {tool_args}")
                self.set_state(AssistantState.EXECUTING)

                from jarvis.tools import registry
                tool_result = registry.execute(tool_name, tool_args)

                # Persist internal execution to history
                self.add_message("assistant", f"Invoking tool {tool_name}.")
                self.add_message("tool", f"Tool '{tool_name}' result: {tool_result}")

                # Build summary prompt for final natural response
                self.set_state(AssistantState.THINKING)
                summary_messages = list(messages)
                summary_messages.append({"role": "assistant", "content": f"I will use {tool_name}."})
                summary_messages.append({
                    "role": "user",
                    "content": (
                        f"[SYSTEM: Tool '{tool_name}' executed. Result:\n{tool_result}\n\n"
                        "Please provide a clean, natural, and concise spoken answer to the user summarizing this result. "
                        "Do not output any ACTION blocks.]"
                    ),
                })

                # Stream the final response to the user
                final_reply = self.ollama.chat_stream(
                    messages=summary_messages,
                    on_token=on_token,
                )
                clean_final = self.clean_final_response(final_reply)

                self.add_message("assistant", clean_final)
                bus.generation_finished.emit(clean_final)
                self.set_state(AssistantState.LISTENING)
                return clean_final

            # Direct response (no tool needed)
            clean_final = self.clean_final_response(raw_reply)
            if on_token:
                on_token(clean_final)

            self.add_message("assistant", clean_final)
            bus.generation_finished.emit(clean_final)

            # Ready for next action / listening
            self.set_state(AssistantState.LISTENING)
            return clean_final

        except OllamaError as err:
            self.set_state(AssistantState.ERROR)
            error_msg = f"LLM Error: {err}"
            logger.error(error_msg)
            bus.generation_error.emit(error_msg)
            return error_msg
        except Exception as exc:
            self.set_state(AssistantState.ERROR)
            error_msg = f"Unexpected error: {exc}"
            logger.exception(error_msg)
            bus.generation_error.emit(error_msg)
            return error_msg

    def stop_generation(self) -> None:
        """Cancel running generation."""
        self.ollama.cancel_current_stream()
        self.set_state(AssistantState.SLEEPING)
