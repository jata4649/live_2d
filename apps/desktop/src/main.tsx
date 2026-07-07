import React from 'react'
import ReactDOM from 'react-dom/client'
import { createHashRouter, RouterProvider } from 'react-router-dom'
import './index.css'
import { AppLayout } from './components/common/AppLayout'
import { ExportPage } from './pages/ExportPage'
import { HomePage } from './pages/HomePage'
import { InterviewPage } from './pages/InterviewPage'
import { MaskEditorPage } from './pages/MaskEditorPage'
import { PartsEditorPage } from './pages/PartsEditorPage'
import { PreviewPage } from './pages/PreviewPage'
import { UploadPage } from './pages/UploadPage'

// Tauri/Electron 化した際に file:// でも動くよう HashRouter を使う
const router = createHashRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/projects/new', element: <UploadPage /> },
      { path: '/projects/:id/interview', element: <InterviewPage /> },
      { path: '/projects/:id/parts', element: <PartsEditorPage /> },
      { path: '/projects/:id/mask/:partId', element: <MaskEditorPage /> },
      { path: '/projects/:id/preview', element: <PreviewPage /> },
      { path: '/projects/:id/export', element: <ExportPage /> },
    ],
  },
])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
