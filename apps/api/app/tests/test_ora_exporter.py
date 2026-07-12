"""OpenRaster (.ora) エクスポータのテスト。"""
from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image

from app.exporters.openraster_exporter import OpenRasterExporter
from app.models.parts import Part, PartsPlan
from app.models.project import Project, SourceImage


def _make_project(tmp_path, size=(64, 64)):
    layers_dir = tmp_path / "layers"
    layers_dir.mkdir()

    def layer(part_id: str, color, region):
        rgba = np.zeros((size[1], size[0], 4), np.uint8)
        y0, y1, x0, x1 = region
        rgba[y0:y1, x0:x1] = color
        Image.fromarray(rgba, "RGBA").save(layers_dir / f"{part_id}.png")

    layer("front_hair_01", (255, 0, 0, 255), (0, 32, 0, 32))
    layer("face_base", (0, 255, 0, 255), (16, 48, 16, 48))
    layer("back_hair", (0, 0, 255, 255), (32, 64, 32, 64))

    parts = PartsPlan(parts=[
        Part(id="front_hair_01", name_jp="前髪", name_en="Front Hair",
             group="Hair/Front", z_order=120),
        Part(id="face_base", name_jp="顔", name_en="Face Base",
             group="Face", z_order=70),
        Part(id="back_hair", name_jp="後ろ髪", name_en="Back Hair",
             group="Hair/Back", z_order=10, visible=False),
    ])
    project = Project(
        project_id="p", name="test",
        source_image=SourceImage(width=size[0], height=size[1]),
    )
    return project, parts, layers_dir


def test_ora_structure_and_order(tmp_path):
    project, parts, layers_dir = _make_project(tmp_path)
    out = tmp_path / "out.ora"
    result = OpenRasterExporter().export(project, parts, layers_dir, out)
    assert result.ok, result.error

    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        # mimetype は先頭・無圧縮
        assert names[0] == "mimetype"
        info = zf.getinfo("mimetype")
        assert info.compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype") == b"image/openraster"
        assert "stack.xml" in names
        assert "mergedimage.png" in names
        assert "Thumbnails/thumbnail.png" in names

        root = ET.fromstring(zf.read("stack.xml"))
        assert root.tag == "image"
        assert root.get("w") == "64" and root.get("h") == "64"

        top_stack = root.find("stack")
        # 最初の子 = 最前面。z_order 降順で Hair(Front) が先頭
        children = list(top_stack)
        assert children[0].tag == "stack" and children[0].get("name") == "Hair"
        hair_front = children[0].find("stack")
        assert hair_front.get("name") == "Front"
        layer0 = hair_front.find("layer")
        assert layer0.get("name") == "Front Hair"
        assert layer0.get("composite-op") == "svg:src-over"

        # 非表示レイヤーは visibility=hidden
        hidden = [
            el for el in root.iter("layer") if el.get("name") == "Back Hair"
        ]
        assert hidden and hidden[0].get("visibility") == "hidden"

        # 参照されている data/*.png がすべて存在し、キャンバスサイズと一致
        for el in root.iter("layer"):
            src = el.get("src")
            assert src in names
            img = Image.open(io.BytesIO(zf.read(src)))
            assert img.size == (64, 64)

        # mergedimage: 前髪(赤)が最前面、非表示の後ろ髪(青)は含まれない
        merged = Image.open(io.BytesIO(zf.read("mergedimage.png"))).convert("RGBA")
        assert merged.getpixel((5, 5))[0] == 255      # 赤
        assert merged.getpixel((60, 60))[3] == 0      # 青は非表示 → 透明


def test_ora_fails_without_layers(tmp_path):
    project, parts, _ = _make_project(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    result = OpenRasterExporter().export(project, parts, empty, tmp_path / "o.ora")
    assert not result.ok


def test_ora_endpoint_e2e(client, project_id):
    """解析→マスク→レイヤー生成後、/export/ora で .ora が取得できる。"""
    import time

    client.post(f"/api/v1/projects/{project_id}/analyze", json={"analyzer": "mock"})
    for endpoint in ("segmentation/run", "layers/generate"):
        job = client.post(f"/api/v1/projects/{project_id}/{endpoint}").json()
        for _ in range(300):
            j = client.get(f"/api/v1/jobs/{job['job_id']}").json()
            if j["status"] in ("done", "failed"):
                break
            time.sleep(0.2)

    res = client.post(
        f"/api/v1/projects/{project_id}/export/ora", json={"force": True}
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True

    res = client.get(
        f"/api/v1/projects/{project_id}/export/files/live2d_import.ora"
    )
    assert res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        assert zf.read("mimetype") == b"image/openraster"
        assert "stack.xml" in zf.namelist()
