import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import OverviewPage from './pages/OverviewPage'
import ExplorerPage from './pages/ExplorerPage'
import PatientPage from './pages/PatientPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/overview" replace />} />
        <Route path="overview"         element={<OverviewPage />} />
        <Route path="explorer"         element={<ExplorerPage />} />
        <Route path="patient/:id"      element={<PatientPage />} />
      </Route>
    </Routes>
  )
}
