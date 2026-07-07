あなたはLive2D用VTuberモデルのパーツ設計者です。
画像解析結果とユーザーの回答をもとに、最終的なパーツ設計(parts.json)を作成してください。

画像解析結果:
{{image_analysis_json}}

ユーザーの回答:
{{user_preferences_json}}

標準パーツテンプレート(参考):
{{standard_parts_json}}

要件:
- パーツはLive2Dで動かす単位で分割する
- id は snake_case、左右は _l / _r サフィックス(キャラクター基準)
- group は "Hair/Front" のような "/" 区切り階層
- z_order は大きいほど手前
- 動かした際に下が見えるパーツには needs_inpaint_under: true と理由を付ける
- 各パーツに recommended_live2d_parameters / parent_deformer_hint / physics_hint を付ける
- 品質レベルに応じて粒度を調整する(簡易=粗く、商用=細かく)

出力形式:
parts.json スキーマに準拠した JSON のみ。
