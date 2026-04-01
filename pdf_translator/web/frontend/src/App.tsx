import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ProjectList } from './pages/ProjectList'
import { TranslationView } from './pages/TranslationView'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-950 text-gray-100">
        <header className="border-b border-gray-800 px-6 py-3">
          <a href="/" className="text-lg font-bold text-white">PDF Translator</a>
        </header>
        <Routes>
          <Route path="/" element={<ProjectList />} />
          <Route path="/project/:id" element={<TranslationView />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
