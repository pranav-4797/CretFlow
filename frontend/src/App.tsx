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
 * /campaigns/new     → CreateCampaignPage (Phase 3)
 * /campaigns/:id     → CampaignDetailPage (Phase 3)
 * /settings          → SettingsPage
 * /gmail             → GmailSettingsPage (Phase 8)
 *
 * Additional protected routes will be added in subsequent phases.
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
                  {/* Phase 3: CreateCampaignPage */}
                  <div className="page-container py-8">
                    <h1 className="section-title">Create Campaign</h1>
                    <p className="section-description mt-2 text-amber-600">
                      🚧 Campaign creation is coming in Phase 3.
                    </p>
                  </div>
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
