import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppProvider } from './context'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Solve from './pages/Solve'
import Prepare from './pages/Prepare'
import ValidationPage from './pages/ValidationPage'
import Students from './pages/Students'
import Teachers from './pages/Teachers'
import Courses from './pages/Courses'
import Rooms from './pages/Rooms'
import TimeModel from './pages/TimeModel'
import Classes from './pages/Classes'
import Rules from './pages/Rules'
import TimetablePage from './pages/TimetablePage'
import Excel from './pages/Excel'

export default function App() {
  return (
    <HashRouter>
      <AppProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/prepare" element={<Prepare />} />
            <Route path="/solve" element={<Solve />} />
            <Route path="/validation" element={<ValidationPage />} />
            <Route path="/students" element={<Students />} />
            <Route path="/teachers" element={<Teachers />} />
            <Route path="/courses" element={<Courses />} />
            <Route path="/rooms" element={<Rooms />} />
            <Route path="/time-model" element={<TimeModel />} />
            <Route path="/classes" element={<Classes />} />
            <Route path="/rules" element={<Rules />} />
            <Route path="/timetable/admin" element={<TimetablePage view="admin" />} />
            <Route path="/timetable/student" element={<TimetablePage view="student" />} />
            <Route path="/timetable/teacher" element={<TimetablePage view="teacher" />} />
            <Route path="/timetable/room" element={<TimetablePage view="room" />} />
            <Route path="/excel" element={<Excel />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </AppProvider>
    </HashRouter>
  )
}
