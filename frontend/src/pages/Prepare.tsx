import { BookOpenCheck, CheckCircle2, FileSpreadsheet, ListChecks, UserRound, UsersRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useApp } from '../context'
import PreparationPanel from '../components/PreparationPanel'
import { Card, PageHeader } from '../components/UI'

const HOW = [
  { icon: <UsersRound size={18} />, title: '1. 学生与选科', text: '先有学生和选科，才知道要开哪些课、分哪些班。', link: '/students' },
  { icon: <UserRound size={18} />, title: '2. 教师与任课', text: '录入教师和不可排时间，系统才能避开冲突。', link: '/teachers' },
  { icon: <BookOpenCheck size={18} />, title: '3. 课程、教室与时间', text: '确认课时、教室容量和作息，规则保持默认即可。', link: '/courses' },
  { icon: <FileSpreadsheet size={18} />, title: '4. 检查后排课', text: '排课前检查会告诉你缺什么，再用一键排课生成课表。', link: '/solve' },
]

export default function Prepare() {
  const { scenario } = useApp()
  if (!scenario) return <div className="loading-block">正在加载排课方案…</div>
  return (
    <>
      <PageHeader eyebrow="开始" title="排课准备"
        description="按老师的工作顺序准备数据。每一项都可以直接进入管理页面，不需要先读技术文档。"
        actions={<Link className="btn btn-ghost" to="/excel"><FileSpreadsheet size={15} />整套数据导入 / 导出</Link>} />
      <PreparationPanel />
      <div className="two-col">
        <Card title="推荐顺序" subtitle="第一次使用可以按这个顺序走">
          <div className="how-list">
            {HOW.map(item => (
              <Link className="how-row" to={item.link} key={item.title}>
                <span className="how-icon">{item.icon}</span>
                <div><strong>{item.title}</strong><p>{item.text}</p></div>
                <CheckCircle2 size={16} />
              </Link>
            ))}
          </div>
        </Card>
        <Card title="常见问题" subtitle="不需要懂算法">
          <div className="faq-list">
            <details open><summary>示例数据会变成我的学校数据吗？</summary><p>不会。示例场景有明确标记，创建自己的方案后数据是独立的，示例也不会被覆盖。</p></details>
            <details><summary>导入学生会不会把教师覆盖掉？</summary><p>不会。学生、教师、教室页面分别导入对应表格，只更新该类数据。整套导入在 Excel 数据交换页。</p></details>
            <details><summary>检查说资源不足怎么办？</summary><p>先看提示是缺教师、教室容量还是走班规则冲突。数据不完整和资源不足会分开提示，不会直接报“算法失败”。</p></details>
            <details><summary>排课后还能改数据吗？</summary><p>可以。修改后系统会提示旧课表已过期，需要重新排课，不会把旧结果当成新结果。</p></details>
          </div>
        </Card>
      </div>
    </>
  )
}
