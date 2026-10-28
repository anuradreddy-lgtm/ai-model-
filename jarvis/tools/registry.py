"""Safe allowlisted tool registry with schema validation."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import inspect
from jarvis.core.events import bus
from jarvis.utils.logger import logger


@dataclass
class ToolParameter:
    name: str
    type_: type
    description: str
    required: bool = True
    default: Any = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: List[ToolParameter]
    handler: Callable
    is_consequential: bool = False

    def validate_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and cast incoming arguments against tool parameter specifications."""
        cleaned_args = {}
        for param in self.parameters:
            if param.name in args:
                val = args[param.name]
                try:
                    # Basic type conversion/validation
                    if param.type_ == int:
                        cleaned_args[param.name] = int(val)
                    elif param.type_ == float:
                        cleaned_args[param.name] = float(val)
                    elif param.type_ == bool:
                        if isinstance(val, str):
                            cleaned_args[param.name] = val.lower() in ("true", "1", "yes")
                        else:
                            cleaned_args[param.name] = bool(val)
                    else:
                        cleaned_args[param.name] = str(val)
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"Parameter '{param.name}' must be of type {param.type_.__name__}: {exc}")
            elif param.required:
                raise ValueError(f"Missing required parameter '{param.name}' for tool '{self.name}'.")
            else:
                cleaned_args[param.name] = param.default
        return cleaned_args


class ToolRegistry:
    """Allowlist registry for safe assistant tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Optional[List[ToolParameter]] = None,
        is_consequential: bool = False,
    ) -> Callable:
        """Decorator to register a function as an allowlisted tool."""
        def decorator(func: Callable) -> Callable:
            tool_params = parameters or []
            # Auto-infer string params if none provided
            if not tool_params:
                sig = inspect.signature(func)
                for p_name, p_val in sig.parameters.items():
                    req = p_val.default == inspect.Parameter.empty
                    default_val = None if req else p_val.default
                    t = str if p_val.annotation == inspect.Parameter.empty else p_val.annotation
                    tool_params.append(
                        ToolParameter(
                            name=p_name,
                            type_=t,
                            description=f"Argument {p_name}",
                            required=req,
                            default=default_val,
                        )
                    )

            tool = Tool(
                name=name,
                description=description,
                parameters=tool_params,
                handler=func,
                is_consequential=is_consequential,
            )
            self._tools[name] = tool
            logger.debug(f"Registered tool '{name}'.")
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def get_descriptions(self) -> str:
        """Generate human/LLM readable tool documentation."""
        lines = []
        for tool in self._tools.values():
            param_strs = []
            for p in tool.parameters:
                req_str = "required" if p.required else f"optional, default={p.default}"
                param_strs.append(f"{p.name} ({p.type_.__name__}, {req_str}): {p.description}")
            params_formatted = "; ".join(param_strs) if param_strs else "None"
            lines.append(f"- `{tool.name}`: {tool.description} | Parameters: {params_formatted}")
        return "\n".join(lines)

    def execute(self, name: str, args: Dict[str, Any]) -> str:
        """Validate arguments and safely execute allowlisted tool."""
        tool = self.get_tool(name)
        if not tool:
            err = f"Error: Tool '{name}' is not registered or allowed."
            logger.warning(err)
            return err

        try:
            validated_args = tool.validate_args(args)
            logger.info(f"Executing tool '{name}' with args {validated_args}")
            bus.tool_execution_started.emit(name, validated_args)

            result = tool.handler(**validated_args)
            result_str = str(result)

            logger.info(f"Tool '{name}' finished with result: {result_str[:120]}...")
            bus.tool_execution_finished.emit(name, result_str)
            return result_str

        except Exception as exc:
            err_msg = f"Tool '{name}' execution failed: {exc}"
            logger.error(err_msg)
            bus.tool_execution_finished.emit(name, err_msg)
            return err_msg


# Global tool registry singleton
registry = ToolRegistry()
