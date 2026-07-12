"""group パス("Hair/Front")からレイヤーツリーを構築する共有ロジック。

PSD / OpenRaster など階層構造を持つエクスポータで共用する。
entries は上(手前)から順に渡すこと。グループの順序は初出順 = z 順の近似。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GroupNode:
    name: str
    children: list = field(default_factory=list)  # GroupNode | dict(entry)


def build_tree(entries: list[dict]) -> GroupNode:
    root = GroupNode(name="")
    nodes: dict[str, GroupNode] = {"": root}
    for entry in entries:
        parent = root
        path = ""
        for seg in [s for s in (entry.get("group") or "").split("/") if s]:
            path = f"{path}/{seg}" if path else seg
            if path not in nodes:
                node = GroupNode(name=seg)
                nodes[path] = node
                parent.children.append(node)
            parent = nodes[path]
        parent.children.append(entry)
    return root
