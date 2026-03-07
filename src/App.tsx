import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { EvaluationDashboard } from './pages/EvaluationDashboard'
import { GraphExplorer } from './pages/GraphExplorer'
import { HomeUpload } from './pages/HomeUpload'
import { QueryInterface } from './pages/QueryInterface'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomeUpload />} />
        <Route path="/graph" element={<GraphExplorer />} />
        <Route path="/query" element={<QueryInterface />} />
        <Route path="/evaluation" element={<EvaluationDashboard />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
