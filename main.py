"""CLI entry point for the Mise booking agent."""

import sys
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from agent.core import create_session_agent

console = Console()


def main():
    console.print(Panel.fit(
        "[bold cyan]Mise AI Booking Assistant[/bold cyan]\n"
        "Natural language service search & booking powered by LLM + RAG\n"
        "Type [bold]quit[/bold] or [bold]exit[/bold] to end the conversation.",
        border_style="cyan",
    ))

    agent, store = create_session_agent()
    session_id = "cli-session"

    while True:
        try:
            user_input = console.input("\n[bold green]You:[/bold green] ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if user_input.strip().lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break

        if not user_input.strip():
            continue

        try:
            with console.status("[cyan]Thinking...[/cyan]", spinner="dots"):
                result = agent.invoke(
                    {"input": user_input},
                    config={"configurable": {"session_id": session_id}},
                )

            # Show tool calls in dim for transparency
            if result.get("intermediate_steps"):
                console.print("\n[dim]--- Agent Actions ---[/dim]")
                for action, observation in result["intermediate_steps"]:
                    console.print(f"[dim]  Tool: {action.tool}[/dim]")
                    console.print(f"[dim]  Input: {action.tool_input}[/dim]")
                console.print("[dim]--------------------[/dim]")

            # Show response
            response = result.get("output", "I encountered an issue. Please try again.")
            console.print(f"\n[bold blue]Mise Assistant:[/bold blue] {response}")

        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            console.print("[dim]Please try again or check your configuration.[/dim]")


if __name__ == "__main__":
    main()
