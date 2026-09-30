"""`slidex` command line: serve the API and run evals."""

from __future__ import annotations

from typing import Annotated

import typer
import uvicorn

from slidex.core.config import get_settings

app = typer.Typer(no_args_is_help=True, add_completion=False)
eval_app = typer.Typer(no_args_is_help=True, help="Run live evaluation suites (costs money).")
app.add_typer(eval_app, name="eval")


@app.command()
def serve(
    reload: Annotated[bool, typer.Option(help="Auto-reload on code changes")] = False,
) -> None:
    """Start the backend on 127.0.0.1 (local only)."""
    settings = get_settings()
    uvicorn.run(
        "slidex.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=reload,
    )


@eval_app.command("run")
def eval_run(suite: Annotated[str, typer.Option(help="Suite name in evals/suites")]) -> None:
    """Run an eval suite against live models (implemented in Phase 7)."""
    typer.echo(f"Eval suite '{suite}' is not implemented yet (task T093).")
    raise typer.Exit(code=2)


@eval_app.command("filler")
def eval_filler(doc_id: str) -> None:
    """Check a generated document for filler (implemented with US3)."""
    typer.echo(f"Filler eval for {doc_id} is not implemented yet (task T086).")
    raise typer.Exit(code=2)
