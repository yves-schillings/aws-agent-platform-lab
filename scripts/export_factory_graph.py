"""Export the compiled Factory topology using LangGraph's own drawing API.

No worker is invoked, no gate is approved and no model or AWS call is made.
The PNG renderer sends only the static graph definition to Mermaid.ink.
Existing outputs are refused so earlier diagram corrections remain intact.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from aws_agent_platform_lab.factory import _build_graph


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New PNG output path")
    args = parser.parse_args()
    png = args.output.resolve()
    mermaid = png.with_suffix(".mmd")
    if png.exists() or mermaid.exists():
        parser.error("Choose a new output name; existing diagrams are never overwritten.")

    # A memory checkpointer compiles the same routing without connecting to AWS.
    drawable = _build_graph(InMemorySaver()).get_graph()
    config = {"config": {"flowchart": {"rankSpacing": 10, "nodeSpacing": 10},
                         "themeVariables": {"fontSize": "28px"}}}
    definition = drawable.draw_mermaid(frontmatter_config=config)
    image = drawable.draw_mermaid_png(frontmatter_config=config)
    png.parent.mkdir(parents=True, exist_ok=True)
    with mermaid.open("x", encoding="utf-8") as stream:
        stream.write(definition)
    with png.open("xb") as stream:
        stream.write(image)
    print(f"LangGraph topology: {png}")
    print(f"Mermaid definition: {mermaid}")


if __name__ == "__main__":
    main()
