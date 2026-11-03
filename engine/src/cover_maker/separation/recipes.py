"""Separation recipes: presets as small graphs of model runs.

A recipe has nodes and outputs. A model node runs one model on an input, which
is either the mix (``mix``) or the mix minus a stem produced by an earlier node
(``mix-minus:<node>.<stem>``). An average node averages stems from earlier
nodes. ``outputs`` says which node provides each final stem. Recipes are pruned
to the nodes needed for the stems a job asks for.
"""

from __future__ import annotations

from importlib import resources
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

from ..domain import Preset, Stem

MIX = "mix"
MINUS = "mix-minus:"


class Ref(BaseModel):
    node: str
    stem: Stem

    @classmethod
    def parse(cls, text: str) -> Ref:
        node, _, stem = text.partition(".")
        return cls(node=node, stem=Stem(stem))

    def __str__(self) -> str:
        return f"{self.node}.{self.stem.value}"


class Node(BaseModel):
    id: str
    model: str | None = None
    input: str = MIX
    average: list[str] | None = None
    stem: Stem | None = None

    @model_validator(mode="after")
    def _check_kind(self) -> Node:
        if (self.model is None) == (self.average is None):
            raise ValueError(f"node {self.id}: set exactly one of 'model' or 'average'")
        if self.average is not None and self.stem is None:
            raise ValueError(f"node {self.id}: average nodes need 'stem'")
        return self

    @property
    def kind(self) -> Literal["model", "average"]:
        return "model" if self.model else "average"

    def dependencies(self) -> list[Ref]:
        if self.average is not None:
            return [Ref.parse(item) for item in self.average]
        if self.input.startswith(MINUS):
            return [Ref.parse(self.input.removeprefix(MINUS))]
        return []


class Recipe(BaseModel):
    nodes: list[Node]
    outputs: dict[Stem, str]

    @model_validator(mode="after")
    def _check_refs(self) -> Recipe:
        seen: set[str] = set()
        for node in self.nodes:
            for ref in node.dependencies():
                if ref.node not in seen:
                    raise ValueError(f"node {node.id} depends on later or unknown node {ref.node}")
            seen.add(node.id)
        for stem, ref in self.outputs.items():
            if Ref.parse(ref).node not in seen:
                raise ValueError(f"output {stem} refers to unknown node {ref}")
        return self

    def output_ref(self, stem: Stem) -> Ref:
        return Ref.parse(self.outputs[stem])

    def prune(self, wanted: set[Stem]) -> list[Node]:
        """Nodes needed to produce ``wanted``, in execution order."""
        by_id = {node.id: node for node in self.nodes}
        needed: set[str] = set()
        stack = [self.output_ref(stem).node for stem in wanted]
        while stack:
            node_id = stack.pop()
            if node_id in needed:
                continue
            needed.add(node_id)
            stack.extend(ref.node for ref in by_id[node_id].dependencies())
        return [node for node in self.nodes if node.id in needed]

    def models(self, wanted: set[Stem]) -> set[str]:
        return {node.model for node in self.prune(wanted) if node.model}


def load(preset: Preset) -> Recipe:
    text = (
        resources.files("cover_maker")
        .joinpath(f"data/recipes/{preset.value}.yaml")
        .read_text("utf-8")
    )
    return Recipe.model_validate(yaml.safe_load(text))
