import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import { Toaster } from '@/components/ui/toaster'
import { ProtectedRoute, PublicOnlyRoute } from '@/components/routing/ProtectedRoute'
import { AppLayout } from '@/components/layout/AppLayout'

// Pages
import LandingPage from '@/pages/LandingPage'
import LoginPage from '@/pages/LoginPage'
import SignupPage from '@/pages/SignupPage'
import DashboardPage from '@/pages/DashboardPage'
import CampaignsPage from '@/pages/CampaignsPage'
import SettingsPage from '@/pages/SettingsPage'
import VerifyPage from '@/pages/VerifyPage'
import NotFoundPage from '@/pages/NotFoundPage'
import CreateCampaignPage from '@/pages/CreateCampaignPage'
import AdminPage from '@/pages/AdminPage'

/**
 * Root application component.
 *
 * Routing Structure:
 * /                  → LandingPage (public)
 * /login             → LoginPage (public-only, redirects if authenticated)
 * /signup            → SignupPage (public-only, redirects if authenticated)
 * /verify/:id        → VerifyPage (public — certificate verification)
 *
 * Protected (require authentication):
 * /dashboard         → DashboardPage
 * /campaigns         → CampaignsPage
 * /campaigns/new     → CreateCampaignPage
 * /settings          → SettingsPage
 * /admin             → AdminPage (Super Admin Control Room)
 */
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/verify/:certificateId" element={<VerifyPage />} />

          {/* Auth routes (redirect to dashboard if already logged in) */}
          <Route element={<PublicOnlyRoute />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
          </Route>

          {/* Protected routes — require authentication */}
          <Route element={<ProtectedRoute />}>
            <Route
              path="/dashboard"
              element={
                <AppLayout>
                  <DashboardPage />
                </AppLayout>
              }
            />
            <Route
              path="/campaigns"
              element={
                <AppLayout>
                  <CampaignsPage />
                </AppLayout>
              }
            />
            <Route
              path="/campaigns/new"
              element={
                <AppLayout>
                  <CreateCampaignPage />
                </AppLayout>
              }
            />
            <Route
              path="/settings"
              element={
                <AppLayout>
                  <SettingsPage />
                </AppLayout>
              }
            />
            <Route
              path="/admin"
              element={
                <AppLayout>
                  <AdminPage />
                </AppLayout>
              }
            />
          </Route>

          {/* 404 */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>

        {/* Global toast notifications */}
        <Toaster />
      </AuthProvider>
    </BrowserRouter>
  )
}
