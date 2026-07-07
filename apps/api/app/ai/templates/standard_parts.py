"""標準VTuberパーツテンプレート。

AI解析が使えない場合(MVP の MockAnalyzer)の出発点となるパーツ一覧。
bbox は正面立ち絵の典型的な比率(画像サイズに対する割合)で初期配置し、
ユーザーが PartsEditor で調整する前提。

タプル: (id, name_jp, name_en, group, z_order, part_type,
         bbox_ratio(x,y,w,h) | None, usage, deformer_hint, physics_hint,
         needs_inpaint_under, inpaint_reason, priority, detail)
detail: "core"=常に生成 / "standard"=standard以上 / "high"=high以上
"""
from __future__ import annotations

from app.models.parts import (
    Live2DInfo,
    Part,
    PartFiles,
    PartType,
    Priority,
    ProcessingSpec,
    QualitySpec,
    SegmentationMethod,
    SegmentationSpec,
)
from app.models.project import MouthType, QualityLevel, UserPreferences

_T = tuple  # 可読性のための別名

_TEMPLATE: list[tuple] = [
    # --- Hair (back) ---
    ("back_hair", "後ろ髪", "Back Hair", "Hair/Back", 10, "hair",
     (0.22, 0.02, 0.56, 0.60), ["ParamAngleX", "PhysicsHairBack"], "D_Hair_Back", "back_hair_soft",
     False, "", "normal", "core"),
    # --- Body ---
    ("torso", "胴体", "Torso", "Body", 20, "body",
     (0.30, 0.38, 0.40, 0.45), ["ParamBodyAngleX", "ParamBodyAngleY", "ParamBodyAngleZ"], "D_Body", "",
     False, "", "high", "core"),
    ("chest", "胸部", "Chest", "Body", 24, "body",
     (0.36, 0.40, 0.28, 0.16), ["ParamBodyAngleX", "PhysicsBody"], "D_Body", "chest_soft",
     True, "体が傾いた際に胴体との境界が見えるため", "normal", "standard"),
    ("shoulder_l", "肩_左", "Shoulder L", "Body/Arm_L", 22, "body",
     (0.58, 0.38, 0.14, 0.12), ["ParamBodyAngleZ"], "D_Arm_L", "",
     False, "", "normal", "standard"),
    ("shoulder_r", "肩_右", "Shoulder R", "Body/Arm_R", 22, "body",
     (0.28, 0.38, 0.14, 0.12), ["ParamBodyAngleZ"], "D_Arm_R", "",
     False, "", "normal", "standard"),
    ("upper_arm_l", "上腕_左", "Upper Arm L", "Body/Arm_L", 21, "body",
     (0.62, 0.44, 0.12, 0.20), ["ParamArmL"], "D_Arm_L", "",
     True, "腕を動かした際に体側面が見えるため", "normal", "standard"),
    ("lower_arm_l", "前腕_左", "Lower Arm L", "Body/Arm_L", 21, "body",
     (0.64, 0.60, 0.12, 0.20), ["ParamArmL"], "D_Arm_L", "",
     False, "", "normal", "standard"),
    ("hand_l", "手_左", "Hand L", "Body/Arm_L", 23, "body",
     (0.64, 0.78, 0.10, 0.10), ["ParamArmL"], "D_Arm_L", "",
     False, "", "normal", "standard"),
    ("upper_arm_r", "上腕_右", "Upper Arm R", "Body/Arm_R", 21, "body",
     (0.26, 0.44, 0.12, 0.20), ["ParamArmR"], "D_Arm_R", "",
     True, "腕を動かした際に体側面が見えるため", "normal", "standard"),
    ("lower_arm_r", "前腕_右", "Lower Arm R", "Body/Arm_R", 21, "body",
     (0.24, 0.60, 0.12, 0.20), ["ParamArmR"], "D_Arm_R", "",
     False, "", "normal", "standard"),
    ("hand_r", "手_右", "Hand R", "Body/Arm_R", 23, "body",
     (0.26, 0.78, 0.10, 0.10), ["ParamArmR"], "D_Arm_R", "",
     False, "", "normal", "standard"),
    # --- Clothes ---
    ("skirt", "スカート", "Skirt", "Clothes", 40, "clothes",
     (0.28, 0.62, 0.44, 0.24), ["ParamBodyAngleX", "PhysicsClothes"], "D_Body", "skirt_soft",
     False, "", "normal", "standard"),
    ("shirt", "シャツ", "Shirt", "Clothes", 42, "clothes",
     (0.32, 0.38, 0.36, 0.26), ["ParamBodyAngleX"], "D_Body", "",
     False, "", "normal", "core"),
    ("jacket", "ジャケット", "Jacket", "Clothes", 44, "clothes",
     (0.28, 0.36, 0.44, 0.32), ["ParamBodyAngleX"], "D_Body", "",
     False, "", "normal", "standard"),
    ("sleeve_l", "袖_左", "Sleeve L", "Clothes", 46, "clothes",
     (0.60, 0.42, 0.14, 0.24), ["ParamArmL"], "D_Arm_L", "sleeve_soft",
     False, "", "normal", "high"),
    ("sleeve_r", "袖_右", "Sleeve R", "Clothes", 46, "clothes",
     (0.26, 0.42, 0.14, 0.24), ["ParamArmR"], "D_Arm_R", "sleeve_soft",
     False, "", "normal", "high"),
    ("collar", "襟", "Collar", "Clothes", 48, "clothes",
     (0.40, 0.34, 0.20, 0.08), ["ParamBodyAngleX"], "D_Body", "",
     False, "", "normal", "standard"),
    ("ribbon", "リボン", "Ribbon", "Clothes", 50, "clothes",
     (0.44, 0.37, 0.12, 0.08), ["PhysicsAccessory"], "D_Body", "ribbon_soft",
     True, "リボンが揺れた際に下の服が見えるため", "normal", "standard"),
    ("clothing_shadow", "服の影", "Clothing Shadow", "Clothes", 41, "clothes",
     None, [], "D_Body", "",
     False, "", "low", "high"),
    # --- Neck / Face base ---
    ("neck", "首", "Neck", "Face", 60, "face",
     (0.44, 0.30, 0.12, 0.10), ["ParamAngleZ"], "D_Head", "",
     True, "頭が傾いた際に首の付け根が見えるため", "high", "core"),
    ("face_base", "顔ベース", "Face Base", "Face", 70, "face",
     (0.34, 0.06, 0.32, 0.26), ["ParamAngleX", "ParamAngleY", "ParamAngleZ"], "D_Head", "",
     True, "前髪が揺れた際に額が見えるため", "high", "core"),
    ("ear_l", "耳_左", "Ear L", "Face", 68, "face",
     (0.62, 0.16, 0.06, 0.08), ["ParamAngleX"], "D_Head", "",
     False, "", "normal", "standard"),
    ("ear_r", "耳_右", "Ear R", "Face", 68, "face",
     (0.32, 0.16, 0.06, 0.08), ["ParamAngleX"], "D_Head", "",
     False, "", "normal", "standard"),
    ("face_shadow", "顔の影", "Face Shadow", "Face", 72, "face",
     None, ["ParamAngleX"], "D_Head", "",
     False, "", "low", "high"),
    ("chin_line", "あごライン", "Chin Line", "Face", 71, "face",
     None, ["ParamAngleY"], "D_Head", "",
     False, "", "low", "high"),
    # --- Mouth ---
    ("mouth_shadow", "口の影", "Mouth Shadow", "Mouth", 88, "mouth",
     None, ["ParamMouthOpenY"], "D_Mouth", "",
     False, "", "low", "high"),
    ("inner_mouth", "口内", "Inner Mouth", "Mouth", 89, "mouth",
     (0.46, 0.275, 0.08, 0.035), ["ParamMouthOpenY"], "D_Mouth", "",
     True, "口を開けた際の口内が必要なため", "high", "core"),
    ("teeth", "歯", "Teeth", "Mouth", 90, "mouth",
     (0.465, 0.275, 0.07, 0.02), ["ParamMouthOpenY"], "D_Mouth", "",
     True, "口を開けた際の歯の描画が必要なため", "normal", "standard"),
    ("tongue", "舌", "Tongue", "Mouth", 90, "mouth",
     (0.47, 0.285, 0.06, 0.02), ["ParamMouthOpenY"], "D_Mouth", "",
     True, "口を大きく開けた際の舌が必要なため", "normal", "high"),
    ("lower_lip", "下唇", "Lower Lip", "Mouth", 91, "mouth",
     (0.455, 0.29, 0.09, 0.02), ["ParamMouthOpenY", "ParamMouthForm"], "D_Mouth", "",
     False, "", "high", "standard"),
    ("upper_lip", "上唇", "Upper Lip", "Mouth", 91, "mouth",
     (0.455, 0.265, 0.09, 0.02), ["ParamMouthOpenY", "ParamMouthForm"], "D_Mouth", "",
     False, "", "high", "standard"),
    ("mouth_line", "口ライン", "Mouth Line", "Mouth", 92, "mouth",
     (0.45, 0.27, 0.10, 0.04), ["ParamMouthOpenY", "ParamMouthForm"], "D_Mouth", "",
     False, "", "high", "core"),
    # --- Eye L (キャラクター基準の左 = 画面向かって右) ---
    ("eye_white_l", "白目_左", "Eye White L", "Eye_L", 90, "eye",
     (0.52, 0.185, 0.09, 0.05), ["ParamEyeLOpen"], "D_Eye_L", "",
     True, "目線移動時に見える白目領域の補完が必要なため", "high", "core"),
    ("iris_l", "虹彩_左", "Iris L", "Eye_L", 91, "eye",
     (0.545, 0.19, 0.05, 0.045), ["ParamEyeBallX", "ParamEyeBallY"], "D_Eye_L", "",
     False, "", "high", "core"),
    ("pupil_l", "瞳孔_左", "Pupil L", "Eye_L", 92, "eye",
     (0.555, 0.198, 0.03, 0.03), ["ParamEyeBallX", "ParamEyeBallY"], "D_Eye_L", "",
     False, "", "normal", "standard"),
    ("eye_highlight_l", "ハイライト_左", "Eye Highlight L", "Eye_L", 93, "eye",
     (0.55, 0.19, 0.025, 0.02), ["ParamEyeBallX", "ParamEyeBallY"], "D_Eye_L", "",
     False, "", "high", "standard"),
    ("lower_lash_l", "下まつげ_左", "Lower Lash L", "Eye_L", 94, "eye",
     (0.52, 0.225, 0.09, 0.015), ["ParamEyeLOpen"], "D_Eye_L", "",
     False, "", "normal", "standard"),
    ("upper_lash_l", "上まつげ_左", "Upper Lash L", "Eye_L", 95, "eye",
     (0.515, 0.175, 0.10, 0.025), ["ParamEyeLOpen"], "D_Eye_L", "",
     False, "", "high", "core"),
    ("eyelid_l", "まぶた_左", "Eyelid L", "Eye_L", 96, "eye",
     (0.515, 0.17, 0.10, 0.02), ["ParamEyeLOpen"], "D_Eye_L", "",
     False, "", "normal", "standard"),
    ("eyebrow_l", "眉_左", "Eyebrow L", "Eye_L", 100, "eyebrow",
     (0.52, 0.145, 0.09, 0.02), ["ParamBrowLY", "ParamBrowLForm"], "D_Brow_L", "",
     False, "", "high", "core"),
    # --- Eye R ---
    ("eye_white_r", "白目_右", "Eye White R", "Eye_R", 90, "eye",
     (0.39, 0.185, 0.09, 0.05), ["ParamEyeROpen"], "D_Eye_R", "",
     True, "目線移動時に見える白目領域の補完が必要なため", "high", "core"),
    ("iris_r", "虹彩_右", "Iris R", "Eye_R", 91, "eye",
     (0.405, 0.19, 0.05, 0.045), ["ParamEyeBallX", "ParamEyeBallY"], "D_Eye_R", "",
     False, "", "high", "core"),
    ("pupil_r", "瞳孔_右", "Pupil R", "Eye_R", 92, "eye",
     (0.415, 0.198, 0.03, 0.03), ["ParamEyeBallX", "ParamEyeBallY"], "D_Eye_R", "",
     False, "", "normal", "standard"),
    ("eye_highlight_r", "ハイライト_右", "Eye Highlight R", "Eye_R", 93, "eye",
     (0.41, 0.19, 0.025, 0.02), ["ParamEyeBallX", "ParamEyeBallY"], "D_Eye_R", "",
     False, "", "high", "standard"),
    ("lower_lash_r", "下まつげ_右", "Lower Lash R", "Eye_R", 94, "eye",
     (0.39, 0.225, 0.09, 0.015), ["ParamEyeROpen"], "D_Eye_R", "",
     False, "", "normal", "standard"),
    ("upper_lash_r", "上まつげ_右", "Upper Lash R", "Eye_R", 95, "eye",
     (0.385, 0.175, 0.10, 0.025), ["ParamEyeROpen"], "D_Eye_R", "",
     False, "", "high", "core"),
    ("eyelid_r", "まぶた_右", "Eyelid R", "Eye_R", 96, "eye",
     (0.385, 0.17, 0.10, 0.02), ["ParamEyeROpen"], "D_Eye_R", "",
     False, "", "normal", "standard"),
    ("eyebrow_r", "眉_右", "Eyebrow R", "Eye_R", 100, "eyebrow",
     (0.39, 0.145, 0.09, 0.02), ["ParamBrowRY", "ParamBrowRForm"], "D_Brow_R", "",
     False, "", "high", "core"),
    # --- Hair (side / front) ---
    ("side_hair_l_01", "横髪_左01", "Side Hair L 01", "Hair/Side_L", 110, "hair",
     (0.60, 0.08, 0.14, 0.40), ["ParamAngleX", "PhysicsHairSide"], "D_Hair_Side_L", "side_hair_soft",
     True, "横髪が揺れた際に頬・首が見えるため", "normal", "core"),
    ("side_hair_r_01", "横髪_右01", "Side Hair R 01", "Hair/Side_R", 110, "hair",
     (0.26, 0.08, 0.14, 0.40), ["ParamAngleX", "PhysicsHairSide"], "D_Hair_Side_R", "side_hair_soft",
     True, "横髪が揺れた際に頬・首が見えるため", "normal", "core"),
    ("hair_shadow", "髪の影", "Hair Shadow", "Hair", 115, "hair",
     None, ["ParamAngleX"], "D_Head", "",
     False, "", "low", "high"),
    ("front_hair_01", "前髪_中央01", "Front Hair 01", "Hair/Front", 120, "hair",
     (0.40, 0.03, 0.20, 0.20), ["ParamAngleX", "ParamAngleY", "PhysicsHairFront"], "D_Hair_Front", "front_hair_soft",
     True, "前髪が揺れた際に額が見えるため", "high", "core"),
    ("front_hair_02", "前髪_左02", "Front Hair 02", "Hair/Front", 121, "hair",
     (0.52, 0.04, 0.14, 0.18), ["ParamAngleX", "PhysicsHairFront"], "D_Hair_Front", "front_hair_soft",
     True, "前髪が揺れた際に額が見えるため", "normal", "standard"),
    ("front_hair_03", "前髪_右03", "Front Hair 03", "Hair/Front", 121, "hair",
     (0.34, 0.04, 0.14, 0.18), ["ParamAngleX", "PhysicsHairFront"], "D_Hair_Front", "front_hair_soft",
     True, "前髪が揺れた際に額が見えるため", "normal", "standard"),
    ("hair_highlight", "髪のハイライト", "Hair Highlight", "Hair", 125, "hair",
     None, [], "D_Head", "",
     False, "", "low", "high"),
    ("ahoge", "アホ毛", "Ahoge", "Hair", 135, "hair",
     (0.45, 0.01, 0.10, 0.08), ["PhysicsAhoge"], "D_Head", "ahoge_soft",
     False, "", "normal", "standard"),
]

# アクセサリー: preferences.accessories に応じて追加
_ACCESSORY_TEMPLATE: dict[str, tuple] = {
    "hairpin": ("hairpin", "ヘアピン", "Hairpin", "Accessories", 140, "accessory",
                (0.36, 0.08, 0.06, 0.04), ["PhysicsAccessory"], "D_Head", "",
                True, "髪が揺れた際に下の髪が見えるため", "normal"),
    "earring_l": ("earring_l", "イヤリング_左", "Earring L", "Accessories", 140, "accessory",
                  (0.63, 0.22, 0.04, 0.05), ["PhysicsAccessory"], "D_Head", "earring_swing",
                  False, "", "normal"),
    "earring_r": ("earring_r", "イヤリング_右", "Earring R", "Accessories", 140, "accessory",
                  (0.33, 0.22, 0.04, 0.05), ["PhysicsAccessory"], "D_Head", "earring_swing",
                  False, "", "normal"),
    "necklace": ("necklace", "ネックレス", "Necklace", "Accessories", 141, "accessory",
                 (0.42, 0.35, 0.16, 0.06), ["PhysicsAccessory"], "D_Body", "necklace_swing",
                 False, "", "normal"),
    "glasses": ("glasses", "メガネ", "Glasses", "Accessories", 145, "accessory",
                (0.36, 0.17, 0.28, 0.08), ["ParamAngleX", "ParamAngleY"], "D_Head", "",
                True, "メガネの下の目元が必要なため", "high"),
    "hat": ("hat", "帽子", "Hat", "Accessories", 150, "accessory",
            (0.30, 0.00, 0.40, 0.14), ["ParamAngleX", "ParamAngleY"], "D_Head", "",
            True, "帽子の下の髪・額が必要なため", "normal"),
}

_DETAIL_RANK = {"core": 0, "standard": 1, "high": 2}
_LEVEL_RANK = {
    QualityLevel.draft: 0,
    QualityLevel.standard: 1,
    QualityLevel.high: 2,
    QualityLevel.commercial: 2,
}


def _ratio_to_bbox(ratio: tuple | None, width: int, height: int) -> list[int] | None:
    if ratio is None:
        return None
    x, y, w, h = ratio
    return [round(x * width), round(y * height), max(1, round(w * width)), max(1, round(h * height))]


def _build_part(row: tuple, width: int, height: int) -> Part:
    (pid, jp, en, group, z, ptype, ratio, usage, deformer, physics,
     inpaint, reason, priority) = row[:13]
    bbox = _ratio_to_bbox(ratio, width, height)
    return Part(
        id=pid,
        name_jp=jp,
        name_en=en,
        group=group,
        z_order=z,
        required=_DETAIL_RANK.get(row[13] if len(row) > 13 else "standard", 1) == 0,
        part_type=PartType(ptype),
        segmentation=SegmentationSpec(
            method=SegmentationMethod.manual_box if bbox else SegmentationMethod.manual_box,
            bbox=bbox,
            text_prompt=en.lower(),
        ),
        files=PartFiles(
            mask_path=f"masks/{pid}_mask.png",
            layer_path=f"layers/{pid}.png",
        ),
        live2d=Live2DInfo(
            usage=list(usage),
            parent_deformer_hint=deformer,
            physics_hint=physics,
        ),
        processing=ProcessingSpec(
            overlap_bleed_px=8 if inpaint else 4,
            edge_feather_px=1,
            needs_inpaint_under=inpaint,
            inpaint_reason=reason,
        ),
        quality=QualitySpec(
            priority=Priority(priority),
            manual_review_required=(priority == "high"),
        ),
    )


def build_standard_parts(
    preferences: UserPreferences, width: int, height: int
) -> list[Part]:
    """品質レベルとヒアリング回答に応じた標準パーツ一覧を返す。"""
    level = _LEVEL_RANK[preferences.quality_level]
    parts: list[Part] = []

    for row in _TEMPLATE:
        detail = row[13]
        if _DETAIL_RANK[detail] > level:
            continue
        pid = row[0]
        # ヒアリング回答による調整
        if pid in ("teeth", "tongue") and preferences.mouth_type == MouthType.open_close:
            continue
        if pid in ("upper_arm_l", "lower_arm_l", "hand_l", "upper_arm_r",
                   "lower_arm_r", "hand_r", "sleeve_l", "sleeve_r") and not preferences.arm_movement:
            # 腕を動かさない場合は胴体に含める(パーツ数削減)
            continue
        if pid == "ahoge" and not preferences.hair_physics:
            continue
        parts.append(_build_part(row, width, height))

    for acc in preferences.accessories:
        key = acc.lower()
        if key == "earring":  # 単数指定は左右に展開
            for k in ("earring_l", "earring_r"):
                parts.append(_build_part(_ACCESSORY_TEMPLATE[k] + ("standard",), width, height))
        elif key in _ACCESSORY_TEMPLATE:
            parts.append(_build_part(_ACCESSORY_TEMPLATE[key] + ("standard",), width, height))

    return parts
