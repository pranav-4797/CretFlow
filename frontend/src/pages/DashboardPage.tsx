import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  Award,
  Mail,
  Users,
  TrendingUp,
  AlertCircle,
  Plus,
  ArrowRight,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Link } from 'react-router-dom'

const statCards = [
  {
    label: 'Total Campaigns',
    value: '—',
    icon: LayoutDashboard,
    color: 'text-violet-500',
    bg: 'bg-violet-500/10',
    change: 'No campaigns yet',
  },
  {
    label: 'Total Participants',
    value: '—',
    icon: Users,
    color: 'text-blue-500',
    bg: 'bg-blue-500/10',
    change: 'Import your first Excel file',
  },
  {
    label: 'Certificates Generated',
    value: '—',
    icon: Award,
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
    change: 'Design your first template',
  },
  {
    label: 'Emails Sent',
    value: '—',
    icon: Mail,
    color: 'text-amber-500',
    bg: 'bg-amber-500/10',
    change: 'Connect Gmail to get started',
  },
]

export default function DashboardPage() {
  return (
    <div className="page-container py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}>
          <h1 className="section-title">Dashboard</h1>
          <p className="section-description">Welcome to CertFlow — your certificate management hub.</p>
        </motion.div>
        <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}>
          <Link to="/campaigns/new">
            <Button variant="gradient" className="gap-2">
              <Plus className="h-4 w-4" />
              New Campaign
            </Button>
          </Link>
        </motion.div>
      </div>

      {/* Phase 1 notice */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6 rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-4 flex items-start gap-3"
      >
        <AlertCircle className="h-5 w-5 text-amber-500 mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
            Phase 1 — Foundation Complete
          </p>
          <p className="text-sm text-amber-700 dark:text-amber-400 mt-0.5">
            Frontend structure, routing, and design system are ready. Authenticate with Firebase (Phase 2) to start creating campaigns.
          </p>
        </div>
      </motion.div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statCards.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.07 }}
          >
            <Card className="hover:shadow-card-hover transition-shadow">
              <CardContent className="pt-6">
                <div className="flex items-start justify-between mb-3">
                  <div className={`inline-flex h-10 w-10 items-center justify-center rounded-xl ${stat.bg}`}>
                    <stat.icon className={`h-5 w-5 ${stat.color}`} />
                  </div>
                </div>
                <div className="text-2xl font-bold mb-1 text-muted-foreground">{stat.value}</div>
                <div className="text-sm font-medium mb-1">{stat.label}</div>
                <div className="text-xs text-muted-foreground">{stat.change}</div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Empty state — Campaigns */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              Recent Campaigns
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl certflow-gradient mb-4">
                <Award className="h-8 w-8 text-white" />
              </div>
              <h3 className="font-semibold text-lg mb-2">No campaigns yet</h3>
              <p className="text-muted-foreground text-sm max-w-xs mb-6">
                Create your first campaign to start generating and distributing certificates.
              </p>
              <Link to="/campaigns/new">
                <Button variant="gradient" className="gap-2">
                  Create First Campaign
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}
