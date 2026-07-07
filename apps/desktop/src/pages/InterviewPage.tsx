import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useJobStore } from '../stores/jobStore'
import { usePartsStore } from '../stores/partsStore'
import { useProjectStore } from '../stores/projectStore'
import type { EyeType, FaceRange, MouthType, QualityLevel, UserPreferences } from '../types'

const DEFAULT_PREFS: UserPreferences = {
  quality_level: 'standard',
  target: 'VTube Studio',
  face_range: 'medium',
  mouth_type: 'auto',
  eye_type: 'full',
  hair_physics: true,
  accessory_physics: true,
  arm_movement: false,
  expression_variants: false,
  accessories: [],
}

const ACCESSORY_OPTIONS = [
  { value: 'hairpin', label: 'ヘアピン' },
  { value: 'earring', label: 'イヤリング' },
  { value: 'necklace', label: 'ネックレス' },
  { value: 'glasses', label: 'メガネ' },
  { value: 'hat', label: '帽子' },
]

export function InterviewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { current, loadProject, savePreferences } = useProjectStore()
  const analyze = usePartsStore((s) => s.analyze)
  const log = useJobStore((s) => s.log)
  const [prefs, setPrefs] = useState<UserPreferences>(DEFAULT_PREFS)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (id && current?.project_id !== id) {
      void loadProject(id).then((p) => setPrefs(p.preferences))
    } else if (current) {
      setPrefs(current.preferences)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const set = <K extends keyof UserPreferences>(key: K, value: UserPreferences[K]) =>
    setPrefs((p) => ({ ...p, [key]: value }))

  const submit = async () => {
    if (!id) return
    setBusy(true)
    setError(null)
    try {
      await savePreferences(prefs)
      log('ヒアリング回答を保存しました')
      await analyze(id)
      log('AI解析(パーツ設計)が完了しました')
      navigate(`/projects/${id}/parts`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl p-8">
      <h1 className="mb-2 text-2xl font-bold">ヒアリング</h1>
      <p className="mb-8 text-sm text-neutral-400">
        回答に応じてパーツ分けの粒度と構成を調整します。あとから変更もできます。
      </p>

      <div className="space-y-6">
        <Segmented
          label="品質レベル"
          value={prefs.quality_level}
          onChange={(v) => set('quality_level', v as QualityLevel)}
          options={[
            { value: 'draft', label: '簡易' },
            { value: 'standard', label: '標準' },
            { value: 'high', label: '高品質' },
            { value: 'commercial', label: '商用品質' },
          ]}
        />
        <div>
          <Label>使用目的</Label>
          <select
            value={prefs.target}
            onChange={(e) => set('target', e.target.value)}
            className="rounded border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm"
          >
            {['VTube Studio', 'nizima', 'ゲーム', '配信', 'その他'].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </div>
        <Segmented
          label="顔の可動域"
          value={prefs.face_range}
          onChange={(v) => set('face_range', v as FaceRange)}
          options={[
            { value: 'small', label: '小' },
            { value: 'medium', label: '中' },
            { value: 'large', label: '大' },
          ]}
        />
        <Segmented
          label="目の仕様"
          value={prefs.eye_type}
          onChange={(v) => set('eye_type', v as EyeType)}
          options={[
            { value: 'blink', label: '瞬きのみ' },
            { value: 'gaze', label: '目線移動あり' },
            { value: 'full', label: '笑顔目・ジト目まで' },
          ]}
        />
        <Segmented
          label="口の仕様"
          value={prefs.mouth_type}
          onChange={(v) => set('mouth_type', v as MouthType)}
          options={[
            { value: 'open_close', label: '開閉のみ' },
            { value: 'aiueo', label: 'あいうえお' },
            { value: 'singing', label: '歌唱向け' },
            { value: 'auto', label: 'おまかせ' },
          ]}
        />
        <Toggle
          label="髪揺れ物理(前髪・横髪・後ろ髪・アホ毛)"
          checked={prefs.hair_physics}
          onChange={(v) => set('hair_physics', v)}
        />
        <div>
          <Label>揺らしたい装飾(複数選択可)</Label>
          <div className="flex flex-wrap gap-2">
            {ACCESSORY_OPTIONS.map((opt) => {
              const on = prefs.accessories.includes(opt.value)
              return (
                <button
                  key={opt.value}
                  onClick={() =>
                    set(
                      'accessories',
                      on
                        ? prefs.accessories.filter((a) => a !== opt.value)
                        : [...prefs.accessories, opt.value],
                    )
                  }
                  className={`rounded-full px-3 py-1 text-sm ${
                    on ? 'bg-indigo-600' : 'bg-neutral-700 hover:bg-neutral-600'
                  }`}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>
        </div>
        <Toggle
          label="腕を動かす"
          checked={prefs.arm_movement}
          onChange={(v) => set('arm_movement', v)}
        />
        <Toggle
          label="表情差分が必要"
          checked={prefs.expression_variants}
          onChange={(v) => set('expression_variants', v)}
        />
      </div>

      {error && <p className="mt-6 text-sm text-red-400">{error}</p>}

      <button
        disabled={busy}
        onClick={() => void submit()}
        className="mt-8 rounded bg-indigo-600 px-6 py-2 font-medium hover:bg-indigo-500 disabled:opacity-40"
      >
        {busy ? 'AI解析中...' : '保存してAI解析を実行'}
      </button>
    </div>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return <div className="mb-2 text-sm font-medium text-neutral-300">{children}</div>
}

function Segmented({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <div>
      <Label>{label}</Label>
      <div className="inline-flex overflow-hidden rounded border border-neutral-600">
        {options.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            className={`px-4 py-1.5 text-sm ${
              value === opt.value ? 'bg-indigo-600' : 'bg-neutral-800 hover:bg-neutral-700'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <label className="flex cursor-pointer items-center gap-3">
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`h-6 w-11 rounded-full p-0.5 transition-colors ${
          checked ? 'bg-indigo-600' : 'bg-neutral-600'
        }`}
      >
        <span
          className={`block h-5 w-5 rounded-full bg-white transition-transform ${
            checked ? 'translate-x-5' : ''
          }`}
        />
      </button>
      <span className="text-sm text-neutral-300">{label}</span>
    </label>
  )
}
