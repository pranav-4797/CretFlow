import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  Award,
  Mail,
  Users,
  TrendingUp,
  Plus,
  ArrowRight,
  Clock,
  CheckCircle2,
  FolderOpen,
  Loader2,
  Sparkles,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Link } from 'react-router-dom'
import { api } from '@/services/api'

interface DashboardStats {
  total_campaigns: number
  total_participants: number
  certificates_generated: number
  emails_sent: number
}

interface CampaignSummary {
  id?: string
  campaign_id?: string
  name?: string
  campaign_name?: string
  description?: string
  status?: string
  total_recipients?: number
  sent_count?: number
  created_at?: string
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>({
    total_campaigns: 0,
    total_participants: 0,
    certificates_generated: 0,
    emails_sent: 0,
  })
  const [recentCampaigns, setRecentCampaigns] = useState<CampaignSummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadDashboard() {
      try {
        setLoading(true)
        const data = await api.get<{
          total_campaigns: number
          total_participants: number
          certificates_generated: number
          emails_sent: number
          recent_campaigns: CampaignSummary[]
        }>('/api/reports/dashboard')

        if (data) {
          setStats({
            total_campaigns: Number(data.total_campaigns ?? 0),
            total_participants: Number(data.total_participants ?? 0),
            certificates_generated: Number(data.certificates_generated ?? 0),
            emails_sent: Number(data.emails_sent ?? 0),
          })
          setRecentCampaigns(data.recent_campaigns || [])
        }
      } catch (err) {
        console.warn('Dashboard report endpoint failed, attempting fallback to /api/campaigns:', err)
        try {
          const campaigns = await api.get<CampaignSummary[]>('/api/campaigns')
          if (Array.isArray(campaigns)) {
            const totalCamps = campaigns.length
            const totalParts = campaigns.reduce((sum, c) => sum + Number(c.total_recipients || 0), 0)
            const totalSent = campaigns.reduce((sum, c) => sum + Number(c.sent_count || 0), 0)
            setStats({
              total_campaigns: totalCamps,
              total_participants: totalParts,
              certificates_generated: totalSent,
              emails_sent: totalSent,
            })
            setRecentCampaigns(campaigns.slice(0, 6))
          }
        } catch (fallbackErr) {
          console.error('Failed to load campaigns fallback:', fallbackErr)
        }
      } finally {
        setLoading(false)
      }
    }

    loadDashboard()
  }, [])

  const statCards = [
    {
      label: 'Total Campaigns',
      value: loading ? '...' : stats.total_campaigns.toLocaleString(),
      icon: LayoutDashboard,
      color: 'text-violet-500',
      bg: 'bg-violet-500/10',
      sub:
        stats.total_campaigns === 0
          ? 'No campaigns yet'
          : `${stats.total_campaigns} campaign${stats.total_campaigns > 1 ? 's' : ''} organized`,
    },
    {
      label: 'Total Participants',
      value: loading ? '...' : stats.total_participants.toLocaleString(),
      icon: Users,
      color: 'text-blue-500',
      bg: 'bg-blue-500/10',
      sub:
        stats.total_participants === 0
          ? 'Import via Excel or Google Forms'
          : `${stats.total_participants} recipients registered`,
    },
    {
      label: 'Certificates Generated',
      value: loading ? '...' : stats.certificates_generated.toLocaleString(),
      icon: Award,
      color: 'text-emerald-500',
      bg: 'bg-emerald-500/10',
      sub:
        stats.certificates_generated === 0
          ? 'Design and issue credentials'
          : `${stats.certificates_generated} verified certificates`,
    },
    {
      label: 'Emails Sent',
      value: loading ? '...' : stats.emails_sent.toLocaleString(),
      icon: Mail,
      color: 'text-amber-500',
      bg: 'bg-amber-500/10',
      sub:
        stats.emails_sent === 0
          ? 'Connect Gmail for delivery'
          : `${stats.emails_sent} delivered to inboxes`,
    },
  ]

  return (
    <div className="page-container py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="section-title">Dashboard</h1>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
              <Sparkles className="h-3 w-3" /> Live Analytics
            </span>
          </div>
          <p className="section-description">Monitor certificate generation, participant metrics, and email deliveries.</p>
        </motion.div>
        <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}>
          <Link to="/campaigns/new">
            <Button variant="gradient" className="gap-2 shadow-sm">
              <Plus className="h-4 w-4" />
              New Campaign
            </Button>
          </Link>
        </motion.div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statCards.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.07 }}
          >
            <Card className="hover:shadow-card-hover transition-shadow border-border/60">
              <CardContent className="pt-6">
                <div className="flex items-start justify-between mb-3">
                  <div className={`inline-flex h-10 w-10 items-center justify-center rounded-xl ${stat.bg}`}>
                    <stat.icon className={`h-5 w-5 ${stat.color}`} />
                  </div>
                </div>
                <div className="text-3xl font-extrabold tracking-tight mb-1 text-foreground">
                  {stat.value}
                </div>
                <div className="text-sm font-semibold text-foreground/80 mb-0.5">{stat.label}</div>
                <div className="text-xs text-muted-foreground">{stat.sub}</div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Recent Campaigns */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
      >
        <Card className="border-border/60">
          <CardHeader className="flex flex-row items-center justify-between pb-4">
            <div>
              <CardTitle className="flex items-center gap-2 text-lg">
                <TrendingUp className="h-5 w-5 text-primary" />
                Recent Campaigns
              </CardTitle>
              <CardDescription>
                Overview of your recent certificate issuance and distribution campaigns.
              </CardDescription>
            </div>
            {recentCampaigns.length > 0 && (
              <Link to="/campaigns">
                <Button variant="ghost" size="sm" className="gap-1 text-xs text-primary font-medium hover:text-primary">
                  View All Campaigns
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            )}
          </CardHeader>

          <CardContent>
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
                <span className="text-sm font-medium">Fetching real-time analytics...</span>
              </div>
            ) : recentCampaigns.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {recentCampaigns.map((camp) => {
                  const cId = camp.id || camp.campaign_id || ''
                  const cName = camp.name || camp.campaign_name || 'Untitled Campaign'
                  const status = (camp.status || 'draft').toLowerCase()
                  const totalRecipients = camp.total_recipients || 0
                  const sentCount = camp.sent_count || 0

                  return (
                    <div
                      key={cId}
                      className="p-4 rounded-xl border border-border/70 hover:border-primary/50 transition-all bg-card/60 hover:bg-card flex flex-col justify-between space-y-3"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2 mb-1.5">
                          <div className="flex items-center gap-2">
                            <FolderOpen className="h-4 w-4 text-primary shrink-0" />
                            <h4 className="font-semibold text-sm line-clamp-1 text-foreground" title={cName}>
                              {cName}
                            </h4>
                          </div>
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium capitalize shrink-0 ${
                              status === 'completed'
                                ? 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20'
                                : status === 'active' || status === 'sending'
                                ? 'bg-blue-500/10 text-blue-600 border border-blue-500/20'
                                : 'bg-muted text-muted-foreground border border-border'
                            }`}
                          >
                            {status}
                          </span>
                        </div>
                        {camp.description ? (
                          <p className="text-xs text-muted-foreground line-clamp-2">{camp.description}</p>
                        ) : (
                          <p className="text-xs text-muted-foreground/60 italic">No description provided</p>
                        )}
                      </div>

                      <div className="pt-2 border-t border-border/50 flex items-center justify-between text-xs text-muted-foreground">
                        <div className="flex items-center gap-3">
                          <div className="flex items-center gap-1" title="Enrolled participants">
                            <Users className="h-3.5 w-3.5 text-muted-foreground" />
                            <span>{totalRecipients}</span>
                          </div>
                          <div className="flex items-center gap-1" title="Certificates delivered">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                            <span>{sentCount}</span>
                          </div>
                        </div>

                        {camp.created_at && (
                          <div className="flex items-center gap-1 text-[11px]">
                            <Clock className="h-3 w-3" />
                            <span>{new Date(camp.created_at).toLocaleDateString()}</span>
                          </div>
                        )}
                      </div>

                      <Link to="/campaigns" className="w-full">
                        <Button variant="outline" size="sm" className="w-full gap-1.5 text-xs h-8">
                          Manage Campaign
                          <ArrowRight className="h-3 w-3" />
                        </Button>
                      </Link>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl certflow-gradient mb-4">
                  <Award className="h-8 w-8 text-white" />
                </div>
                <h3 className="font-semibold text-lg mb-2">No campaigns yet</h3>
                <p className="text-muted-foreground text-sm max-w-xs mb-6">
                  Create your first campaign to start generating and distributing certificates automatically.
                </p>
                <Link to="/campaigns/new">
                  <Button variant="gradient" className="gap-2">
                    Create First Campaign
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </Link>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}
