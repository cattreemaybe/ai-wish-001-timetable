import { useEffect, useState } from 'react'
import { ArrowRight, Database, FileSpreadsheet, GraduationCap, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context'
import { Modal, Spinner } from './UI'

const KEY = 'aiwish.onboarded.v1'

export default function FirstRunDialog() {
  const { scenarios, setScenarioId, createCustomScenario, notify } = useApp()
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    try {
      setOpen(localStorage.getItem(KEY) !== '1')
    } catch { setOpen(true) }
  }, [])

  const finish = () => {
    try { localStorage.setItem(KEY, '1') } catch { /* ignore */ }
    setOpen(false)
  }

  const useSample = () => {
    const target = scenarios.find(x => x.id === 'F') || scenarios.find(x => x.is_sample) || scenarios[0]
    if (target) setScenarioId(target.id)
    finish()
    navigate('/')
  }

  const createOwn = async () => {
    setCreating(true)
    try {
      const created = await createCustomScenario()
      notify('success', `已创建「${created.name}」。下一步先导入或录入学生、教师和教室。`)
      finish()
      navigate('/prepare')
    } catch (e) {
      notify('error', e instanceof Error ? e.message : String(e))
    } finally { setCreating(false) }
  }

  return (
    <Modal open={open} wide title="欢迎使用智能走班排课" subtitle="第一次使用？先选择一种方式开始。"
      onClose={finish}
      footer={<button className="btn btn-ghost" onClick={finish}>稍后选择，先看看</button>}>
      <div className="first-run-intro">
        <div className="first-run-mark"><GraduationCap size={26} /></div>
        <div>
          <strong>从数据到课表，按老师的工作顺序来</strong>
          <p>示例数据用于体验；创建自己的方案时，数据只保存在本机，不会和示例混在一起。</p>
        </div>
      </div>
      <div className="first-run-choices">
        <button className="first-run-card" onClick={useSample}>
          <div className="choice-icon sample"><Database size={22} /></div>
          <span className="choice-kicker">最快体验</span>
          <strong>使用示例数据体验</strong>
          <p>直接打开综合场景 F：8 个行政班、320 名学生、24 种选科组合。</p>
          <span className="choice-action">加载示例数据 <ArrowRight size={15} /></span>
          <em>示例数据会明确标注，不会当成你的学校数据</em>
        </button>
        <button className="first-run-card primary" onClick={createOwn} disabled={creating}>
          <div className="choice-icon own"><FileSpreadsheet size={22} /></div>
          <span className="choice-kicker">从自己的学校开始</span>
          <strong>创建自己的排课方案</strong>
          <p>从空白方案开始，下载模板后分别导入学生、教师和教室数据。</p>
          <span className="choice-action">{creating ? <Spinner label="创建中" /> : <>创建空白方案 <ArrowRight size={15} /></>}</span>
          <em>支持分项导入，不会覆盖其他类别数据</em>
        </button>
      </div>
      <div className="first-run-tip"><Sparkles size={14} /><span>不需要懂编程或排课算法。首页会告诉你下一步该做什么。</span></div>
    </Modal>
  )
}
