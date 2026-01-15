"""
Teacher Agent Module

A specialized agent for answering questions about the coding process.
This agent has access to project context and can explain:
- What the coder agent is doing
- How code works
- Project structure and files
- AI agent concepts for learning
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .config import Config, load_config
from .llm import LLMInterface
from .memory import Memory
from .context import ProjectContext, get_global_context


@dataclass
class TeacherResponse:
    """Response from teacher agent."""
    answer: str
    sources: List[str]  # Context sources used (files, tools, etc.)
    confidence: float  # 0.0 to 1.0


class TeacherAgent:
    """
    Teacher agent for explaining code and answering questions.

    This agent specializes in educational explanations and has
    access to the project context to provide informed answers.
    """

    # System prompt for the teacher
    SYSTEM_PROMPT = """You are Professor Code, an AI teaching assistant specializing in
explaining software development and AI agent behavior.

Your role is to help users learn by:
1. EXPLAINING CODE: Break down what code does, line by line if needed
2. TEACHING CONCEPTS: Explain programming concepts, patterns, and best practices
3. AGENT INSIGHTS: Explain what the coder agent is doing and why
4. PROJECT GUIDANCE: Help understand project structure and file organization

You have access to the current project context including:
- Project files and their contents
- The coder agent's conversation history
- Recent tool calls (file operations, code execution)
- File tree structure

GUIDELINES:
1. Be patient, clear, and educational - assume the user is learning
2. Use analogies and examples when helpful
3. Break complex explanations into simple steps
4. When discussing the coder agent's actions, explain the reasoning
5. If you're not sure about something, say so - don't make things up
6. Encourage questions and curiosity

SPECIAL COMMANDS:
The user can use special commands prefixed with ! to get specific information:
- !files: List project files
- !tree: Show file tree structure
- !content <file>: Show content of specific file
- !tools: Show recent tool calls by coder agent
- !conv: Show conversation history
- !help: Show available commands

Always respond in a helpful, educational tone. If the user asks about
something outside the project context, say what you can explain based
on general knowledge."""

    def __init__(self, config: Optional[Config] = None, context: Optional[ProjectContext] = None):
        """
        Initialize teacher agent.

        Args:
            config: Configuration object
            context: Project context (uses global context if None)
        """
        self.config = config or load_config()
        self.context = context or get_global_context()

        # Create LLM interface (could use different model than coder agent)
        self.llm = LLMInterface(self.config)

        # Memory for conversation with user
        self.memory = Memory(max_history=20)
        self.memory.set_system_message(self.SYSTEM_PROMPT)

        # Special command handlers
        self._command_handlers = {
            "!files": self._handle_files_command,
            "!tree": self._handle_tree_command,
            "!content": self._handle_content_command,
            "!tools": self._handle_tools_command,
            "!conv": self._handle_conv_command,
            "!help": self._handle_help_command,
        }

    def ask(self, question: str) -> TeacherResponse:
        """
        Ask the teacher agent a question.

        Args:
            question: User's question about the project/code

        Returns:
            TeacherResponse with answer and context sources
        """
        # Check for special commands
        if question.strip().startswith("!"):
            return self._handle_command(question.strip())

        # Build context for the question
        context_info = self._build_context_for_question(question)

        # Format the prompt with context
        prompt = self._format_prompt(question, context_info)

        # Add to memory and get response
        self.memory.add_user_message(prompt)

        try:
            response = self.llm.chat(self.memory.get_messages_for_llm())
            self.memory.add_assistant_message(response)

            return TeacherResponse(
                answer=response,
                sources=context_info.get("sources", []),
                confidence=0.9  # Could be more sophisticated
            )
        except Exception as e:
            error_msg = f"I encountered an error while processing your question: {e}"
            return TeacherResponse(
                answer=error_msg,
                sources=[],
                confidence=0.0
            )

    def _build_context_for_question(self, question: str) -> Dict[str, Any]:
        """
        Build relevant context for a question.

        Args:
            question: User's question

        Returns:
            Dictionary with context information
        """
        context_info = {
            "project_summary": self.context.get_context_summary(),
            "sources": ["project_context"]
        }

        # Extract potential file references from question
        import re
        file_patterns = [
            r'file[:\s]+([\w\./]+)',  # "file: main.py"
            r'([\w/]+\.py\b)',         # "main.py"
            r'([\w/]+\.(txt|md|json|yaml|yml)\b)',  # Other text files
        ]

        referenced_files = []
        for pattern in file_patterns:
            matches = re.findall(pattern, question.lower())
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]  # Get first group
                referenced_files.append(match)

        # Get content for referenced files
        file_contents = {}
        for file_ref in referenced_files[:3]:  # Limit to 3 files
            content = self.context.get_file_content(file_ref)
            if content:
                file_contents[file_ref] = content[:2000]  # Limit content length
                context_info["sources"].append(f"file:{file_ref}")

        if file_contents:
            context_info["file_contents"] = file_contents

        # Check if question is about recent tools
        tool_keywords = ["tool", "action", "did", "executed", "ran", "called"]
        if any(keyword in question.lower() for keyword in tool_keywords):
            recent_tools = self.context.get_recent_tools(limit=5)
            if recent_tools:
                context_info["recent_tools"] = [
                    f"{tool.tool_name}: {tool.result[:200]}..."
                    for tool in recent_tools
                ]
                context_info["sources"].append("recent_tools")

        return context_info

    def _format_prompt(self, question: str, context_info: Dict[str, Any]) -> str:
        """
        Format prompt with context for the LLM.

        Args:
            question: Original question
            context_info: Context information

        Returns:
            Formatted prompt string
        """
        prompt_parts = []

        # Add project summary
        prompt_parts.append("CURRENT PROJECT CONTEXT:")
        prompt_parts.append(context_info.get("project_summary", "No context available"))

        # Add file contents if available
        if "file_contents" in context_info:
            prompt_parts.append("\nREFERENCED FILE CONTENTS:")
            for file_name, content in context_info["file_contents"].items():
                prompt_parts.append(f"\n--- {file_name} ---")
                prompt_parts.append(content)

        # Add recent tools if available
        if "recent_tools" in context_info:
            prompt_parts.append("\nRECENT TOOL CALLS:")
            for i, tool_summary in enumerate(context_info["recent_tools"], 1):
                prompt_parts.append(f"{i}. {tool_summary}")

        # Add the question
        prompt_parts.append(f"\nUSER'S QUESTION: {question}")
        prompt_parts.append("\nPlease provide a helpful, educational answer.")

        return "\n".join(prompt_parts)

    def _handle_command(self, command: str) -> TeacherResponse:
        """
        Handle special commands starting with !.

        Args:
            command: Command string

        Returns:
            TeacherResponse
        """
        parts = command.split()
        cmd = parts[0].lower()

        if cmd in self._command_handlers:
            return self._command_handlers[cmd](parts[1:] if len(parts) > 1 else [])
        else:
            return TeacherResponse(
                answer=f"Unknown command: {cmd}. Type !help for available commands.",
                sources=[],
                confidence=1.0
            )

    def _handle_files_command(self, args: List[str]) -> TeacherResponse:
        """Handle !files command - list project files."""
        file_count = len(self.context.file_states)
        python_files = [f for f in self.context.file_states.keys() if f.endswith('.py')]

        response = f"Project has {file_count} files total.\n"
        response += f"Python files: {len(python_files)}\n\n"

        if args and args[0] == "py":
            # Show only Python files
            response += "Python files:\n"
            for file in sorted(python_files)[:20]:  # Limit to 20
                response += f"  - {file}\n"
            if len(python_files) > 20:
                response += f"  ... and {len(python_files) - 20} more\n"
        else:
            # Show all files (limited)
            response += "Files (showing first 20):\n"
            for i, file in enumerate(sorted(self.context.file_states.keys())[:20]):
                response += f"  - {file}\n"
            if file_count > 20:
                response += f"  ... and {file_count - 20} more\n"

        return TeacherResponse(
            answer=response,
            sources=["file_listing"],
            confidence=1.0
        )

    def _handle_tree_command(self, args: List[str]) -> TeacherResponse:
        """Handle !tree command - show file tree."""
        tree = self.context.get_file_tree()
        tree_str = self._format_tree(tree)

        return TeacherResponse(
            answer=f"Project file tree:\n{tree_str}",
            sources=["file_tree"],
            confidence=1.0
        )

    def _format_tree(self, tree: Dict[str, Any], indent: int = 0) -> str:
        """Format tree structure as string."""
        result = ""
        for name, info in sorted(tree.items()):
            if info["type"] == "dir":
                result += "  " * indent + f"📁 {name}/\n"
                result += self._format_tree(info["children"], indent + 1)
            else:
                size_kb = info["size"] / 1024 if info["size"] > 0 else 0
                result += "  " * indent + f"📄 {name} ({size_kb:.1f} KB)\n"
        return result

    def _handle_content_command(self, args: List[str]) -> TeacherResponse:
        """Handle !content <file> command - show file content."""
        if not args:
            return TeacherResponse(
                answer="Please specify a file: !content <filename>",
                sources=[],
                confidence=1.0
            )

        file_path = args[0]
        content = self.context.get_file_content(file_path)

        if content is None:
            return TeacherResponse(
                answer=f"File '{file_path}' not found or cannot be read.",
                sources=[],
                confidence=1.0
            )

        # Limit content length
        if len(content) > 2000:
            content = content[:2000] + "\n\n... (content truncated, file too large)"

        return TeacherResponse(
            answer=f"Content of '{file_path}':\n\n```\n{content}\n```",
            sources=[f"file:{file_path}"],
            confidence=1.0
        )

    def _handle_tools_command(self, args: List[str]) -> TeacherResponse:
        """Handle !tools command - show recent tool calls."""
        limit = int(args[0]) if args and args[0].isdigit() else 5
        recent_tools = self.context.get_recent_tools(limit=limit)

        if not recent_tools:
            return TeacherResponse(
                answer="No recent tool calls recorded.",
                sources=[],
                confidence=1.0
            )

        response = f"Recent tool calls (last {len(recent_tools)}):\n\n"
        for i, tool in enumerate(recent_tools, 1):
            response += f"{i}. {tool.tool_name}\n"
            response += f"   Time: {tool.timestamp.strftime('%H:%M:%S')}\n"
            if tool.arguments:
                args_str = json.dumps(tool.arguments, indent=2)[:200]
                response += f"   Args: {args_str}\n"
            result_preview = tool.result[:150] + "..." if len(tool.result) > 150 else tool.result
            response += f"   Result: {result_preview}\n\n"

        return TeacherResponse(
            answer=response,
            sources=["tool_history"],
            confidence=1.0
        )

    def _handle_conv_command(self, args: List[str]) -> TeacherResponse:
        """Handle !conv command - show conversation history."""
        conv_summary = self.context.get_conversation_summary()

        return TeacherResponse(
            answer=f"Recent conversation:\n\n{conv_summary}",
            sources=["conversation_history"],
            confidence=1.0
        )

    def _handle_help_command(self, args: List[str]) -> TeacherResponse:
        """Handle !help command - show available commands."""
        help_text = """Available commands:

!files [py] - List project files (add 'py' for only Python files)
!tree - Show file tree structure
!content <filename> - Show content of a file
!tools [N] - Show recent N tool calls (default: 5)
!conv - Show conversation history
!help - Show this help message

Examples:
  !files py      # List Python files
  !content main.py # Show main.py content
  !tools 10      # Show last 10 tool calls

You can also ask natural questions about:
- What code does
- Project structure
- What the coder agent is doing
- Programming concepts"""

        return TeacherResponse(
            answer=help_text,
            sources=[],
            confidence=1.0
        )

    def reset(self) -> None:
        """Reset teacher conversation memory."""
        self.memory.clear()
        self.memory.set_system_message(self.SYSTEM_PROMPT)


# Convenience function
def create_teacher_agent(config: Optional[Config] = None) -> TeacherAgent:
    """Create and return a teacher agent instance."""
    return TeacherAgent(config)