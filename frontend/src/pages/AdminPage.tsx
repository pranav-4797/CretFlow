import { useState, useEffect, useMemo } from 'react'
import {
  ShieldCheck,
  ShieldAlert,
  Database,
  Users,
  Mail,
  FolderOpen,
  RefreshCw,
  Search,
  ExternalLink,
  Trash2,
  Activity,
  CheckCircle2,
  Clock,
  Sparkles,
  FileSpreadsheet,
  RotateCcw,
  ArrowRight,
  TrendingUp,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Link } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { api } from '@/services/api'
import { useToast } from '@/hooks/use-toast'
import { DeleteCampaignDialog, CampaignToDelete } from '@/components/campaigns/DeleteCampaignDialog'

interface AdminOverview {
  total_campaigns: number
  total_participants: number
  total_sent: number
  total_failed: number
  distinct_users_count: number
  firestore_read_metrics: Record<string, number>
  admin_user: string
}

interface AdminCampaign {
  id: string
  campaign_id: string
  name: string
  campaign_name: string
  owner_uid: string
  owner_name: string
  owner_email?: string
  status: string
  total_recipients: number
  sent_count: number
  failed_count: number
  campaign_type: string
  created_at?: string
  description?: string
}

export default function AdminPage() {
  const { user } = useAuth()
  const { toast } = useToast()

  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [campaigns, setCampaigns] = useState<AdminCampaign[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [resettingMetrics, setResettingMetrics] = useState(false)

  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<'all' | 'spreadsheet' | 'google_forms'>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'draft' | 'ready' | 'completed' | 'sending'>('all')
  const [selectedOwner, setSelectedOwner] = useState<string>('all')

  // Deletion modal
  const [campaignToDelete, setCampaignToDelete] = useState<CampaignToDelete | null>(null)

  const fetchData = async () => {
    try {
      setRefreshing(true)
      const [overviewData, campaignsData] = await Promise.all([
        api.get<AdminOverview>('/api/admin/overview'),
        api.get<AdminCampaign[]>('/api/admin/campaigns?limit=500'),
      ])
      setOverview(overviewData)
      setCampaigns(campaignsData || [])
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch admin data'
      toast({
        variant: 'destructive',
        title: 'Super Admin Sync Failed',
        description: msg,
      })
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    if (user?.isAdmin) {
      fetchData()
    } else {
      setLoading(false)
    }
  }, [user])

  const handleResetMetrics = async () => {
    try {
      setResettingMetrics(true)
      await api.post('/api/admin/metrics/reset')
      toast({
        title: 'Telemetry Profiler Reset',
        description: 'Firestore in-memory read counters have been reset to zero.',
      })
      await fetchData()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to reset metrics'
      toast({
        variant: 'destructive',
        title: 'Reset Failed',
        description: msg,
      })
    } finally {
      setResettingMetrics(false)
    }
  }

  const handleCampaignDeleted = (deletedId: string) => {
    setCampaigns((prev) => prev.filter((c) => (c.id || c.campaign_id) !== deletedId))
    setOverview((prev) => {
      if (!prev) return null
      return {
        ...prev,
        total_campaigns: Math.max(0, prev.total_campaigns - 1),
      }
    })
  }

  // Distinct organizers for filtering with human names & emails
  const distinctOrganizers = useMemo(() => {
    const map = new Map<string, { uid: string; name: string; email?: string }>()
    campaigns.forEach((c) => {
      if (c.owner_uid && c.owner_uid !== 'Unknown') {
        if (!map.has(c.owner_uid)) {
          map.set(c.owner_uid, {
            uid: c.owner_uid,
            name: c.owner_name || 'Organizer',
            email: c.owner_email,
          })
        }
      }
    })
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name))
  }, [campaigns])

  // Filtered campaigns
  const filteredCampaigns = useMemo(() => {
    return campaigns.filter((c) => {
      const name = (c.name || c.campaign_name || '').toLowerCase()
      const cid = (c.id || c.campaign_id || '').toLowerCase()
      const ownerName = (c.owner_name || '').toLowerCase()
      const ownerEmail = (c.owner_email || '').toLowerCase()
      const q = searchQuery.toLowerCase().trim()

      const matchesSearch =
        !q ||
        name.includes(q) ||
        cid.includes(q) ||
        ownerName.includes(q) ||
        ownerEmail.includes(q)

      const matchesType = typeFilter === 'all' || (c.campaign_type || 'spreadsheet') === typeFilter
      const matchesStatus = statusFilter === 'all' || (c.status || 'draft').toLowerCase() === statusFilter
      const matchesOwner = selectedOwner === 'all' || c.owner_uid === selectedOwner

      return matchesSearch && matchesType && matchesStatus && matchesOwner
    })
  }, [campaigns, searchQuery, typeFilter, statusFilter, selectedOwner])

  // Non-admin fallback
  if (!user?.isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] px-4 text-center">
        <div className="w-16 h-16 rounded-2xl bg-destructive/10 border border-destructive/20 flex items-center justify-center mb-4 text-destructive">
          <ShieldAlert className="w-8 h-8" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight mb-2">Super Admin Access Required</h1>
        <p className="text-muted-foreground max-w-md mb-6">
          This portal provides unrestricted platform-wide telemetry and campaign controls.
          Signed-in account <code className="text-foreground font-mono bg-muted px-1.5 py-0.5 rounded text-xs">{user?.email || 'Guest'}</code> does not have super administrator privileges.
        </p>
        <Link to="/dashboard">
          <Button variant="default" className="gap-2">
            Back to Dashboard
            <ArrowRight className="w-4 h-4" />
          </Button>
        </Link>
      </div>
    )
  }

  const totalReads = overview?.firestore_read_metrics
    ? Object.values(overview.firestore_read_metrics).reduce((a, b) => a + b, 0)
    : 0

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/50 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-500">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight">Super Admin Control Room</h1>
                <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                  Master Switch Active
                </span>
              </div>
              <p className="text-sm text-muted-foreground mt-0.5">
                Multi-tenant orchestrator, platform campaign management, and live operational telemetry.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchData}
            disabled={refreshing}
            className="gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleResetMetrics}
            disabled={resettingMetrics}
            className="gap-2 border border-border"
          >
            <RotateCcw className={`w-4 h-4 ${resettingMetrics ? 'animate-spin' : ''}`} />
            Reset Profiler
          </Button>
        </div>
      </div>

      {/* Top Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Total Campaigns */}
        <Card className="border-border/60 bg-card/60 backdrop-blur-sm shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Platform Campaigns</span>
              <div className="p-2 rounded-lg bg-primary/10 text-primary">
                <FolderOpen className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-bold tracking-tight">
                {overview ? overview.total_campaigns : '—'}
              </span>
              <p className="text-xs text-muted-foreground mt-1">Across all organizers</p>
            </div>
          </CardContent>
        </Card>

        {/* Total Participants */}
        <Card className="border-border/60 bg-card/60 backdrop-blur-sm shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Total Recipients</span>
              <div className="p-2 rounded-lg bg-blue-500/10 text-blue-500">
                <Users className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-bold tracking-tight">
                {overview ? overview.total_participants.toLocaleString() : '—'}
              </span>
              <p className="text-xs text-muted-foreground mt-1">Global database pool</p>
            </div>
          </CardContent>
        </Card>

        {/* Total Emails Dispatched */}
        <Card className="border-border/60 bg-card/60 backdrop-blur-sm shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Dispatched Emails</span>
              <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-500">
                <Mail className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-bold tracking-tight">
                {overview ? overview.total_sent.toLocaleString() : '—'}
              </span>
              <p className="text-xs text-muted-foreground mt-1">
                {overview && overview.total_failed > 0
                  ? `${overview.total_failed} failed`
                  : '100% clean dispatch'}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Distinct Organizers */}
        <Card className="border-border/60 bg-card/60 backdrop-blur-sm shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Organizers</span>
              <div className="p-2 rounded-lg bg-purple-500/10 text-purple-500">
                <TrendingUp className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-bold tracking-tight">
                {overview ? overview.distinct_users_count : '—'}
              </span>
              <p className="text-xs text-muted-foreground mt-1">Active tenant owners</p>
            </div>
          </CardContent>
        </Card>

        {/* Telemetry Reads */}
        <Card className="border-border/60 bg-card/60 backdrop-blur-sm shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Live Firestore Reads</span>
              <div className="p-2 rounded-lg bg-amber-500/10 text-amber-500">
                <Database className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-bold tracking-tight text-amber-600 dark:text-amber-400">
                {totalReads}
              </span>
              <p className="text-xs text-muted-foreground mt-1">Tracked in-memory</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Telemetry Profiler Breakdown Drawer */}
      <Card className="border-border/60 bg-card/40 backdrop-blur-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-amber-500" />
              <CardTitle className="text-base font-semibold">Live Operational Telemetry & Read Breakdown</CardTitle>
            </div>
            <span className="text-xs font-mono text-muted-foreground bg-muted/60 px-2 py-0.5 rounded border border-border/50">
              Low-RAM Chunking Active (500 per batch)
            </span>
          </div>
          <CardDescription className="text-xs">
            Direct real-time monitor of server-side Firestore operations. Use "Reset Profiler" before executing campaigns to accurately inspect reads.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3 pt-1">
            {overview?.firestore_read_metrics && Object.entries(overview.firestore_read_metrics).length > 0 ? (
              Object.entries(overview.firestore_read_metrics).map(([op, count]) => (
                <div
                  key={op}
                  className="p-3 rounded-lg border border-border/50 bg-background/50 flex flex-col justify-between"
                >
                  <span className="text-[11px] font-mono text-muted-foreground truncate" title={op}>
                    {op}
                  </span>
                  <div className="flex items-baseline justify-between mt-2">
                    <span className="text-lg font-bold font-mono">{count}</span>
                    <span className="text-[10px] text-muted-foreground">ops</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-full py-4 text-center text-xs text-muted-foreground">
                No active read operations tracked in current profiling session.
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Platform Campaigns Master Section */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold tracking-tight">Platform-Wide Campaigns</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Super Admin master controls — inspect, manage, and delete any campaign across all platform organizers.
            </p>
          </div>
          <div className="text-xs font-medium text-muted-foreground">
            Showing <span className="font-bold text-foreground">{filteredCampaigns.length}</span> of {campaigns.length} total campaigns
          </div>
        </div>

        {/* Filters and Controls */}
        <div className="flex flex-wrap items-center gap-3 bg-muted/30 p-3.5 rounded-xl border border-border/50">
          {/* Search Input */}
          <div className="relative flex-1 min-w-[240px]">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search by campaign name, organizer, or email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-9 text-xs bg-background"
            />
          </div>

          {/* Type Filter */}
          <div className="flex items-center gap-1.5 bg-background p-1 rounded-lg border border-border/60">
            <span className="text-[11px] font-medium text-muted-foreground px-2">Type:</span>
            <button
              onClick={() => setTypeFilter('all')}
              className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                typeFilter === 'all'
                  ? 'bg-primary text-primary-foreground font-semibold shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setTypeFilter('spreadsheet')}
              className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                typeFilter === 'spreadsheet'
                  ? 'bg-primary text-primary-foreground font-semibold shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Spreadsheet
            </button>
            <button
              onClick={() => setTypeFilter('google_forms')}
              className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                typeFilter === 'google_forms'
                  ? 'bg-primary text-primary-foreground font-semibold shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Google Forms
            </button>
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-1.5 bg-background p-1 rounded-lg border border-border/60">
            <span className="text-[11px] font-medium text-muted-foreground px-2">Status:</span>
            {(['all', 'draft', 'ready', 'sending', 'completed'] as const).map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-1 text-xs rounded-md capitalize transition-colors ${
                  statusFilter === st
                    ? 'bg-primary text-primary-foreground font-semibold shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Organizer Filter */}
          {distinctOrganizers.length > 0 && (
            <div className="flex items-center gap-1.5 bg-background p-1 rounded-lg border border-border/60">
              <span className="text-[11px] font-medium text-muted-foreground px-2">Organizer:</span>
              <select
                value={selectedOwner}
                onChange={(e) => setSelectedOwner(e.target.value)}
                className="bg-transparent text-xs py-1 px-2 rounded focus:outline-none max-w-[220px]"
              >
                <option value="all">All Organizers</option>
                {distinctOrganizers.map((org) => (
                  <option key={org.uid} value={org.uid}>
                    {org.name} {org.email ? `(${org.email})` : ''}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Campaign List Table */}
        <div className="border border-border/60 rounded-xl overflow-hidden bg-card/60 backdrop-blur-sm shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border/60 bg-muted/40 font-semibold text-muted-foreground">
                  <th className="py-3 px-4">Campaign Name & ID</th>
                  <th className="py-3 px-4">Organizer</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Delivery Progress</th>
                  <th className="py-3 px-4 text-right">Super Admin Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-muted-foreground">
                      <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-primary" />
                      Loading platform campaigns...
                    </td>
                  </tr>
                ) : filteredCampaigns.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-muted-foreground">
                      No campaigns found matching the specified filters.
                    </td>
                  </tr>
                ) : (
                  filteredCampaigns.map((c) => {
                    const cid = c.id || c.campaign_id
                    const cname = c.name || c.campaign_name || 'Untitled Campaign'
                    const isGoogleForm = c.campaign_type === 'google_forms'
                    const isCompleted = c.status?.toLowerCase() === 'completed'
                    const isDraft = c.status?.toLowerCase() === 'draft'

                    return (
                      <tr key={cid} className="hover:bg-muted/20 transition-colors">
                        <td className="py-3.5 px-4">
                          <div className="font-semibold text-foreground">{cname}</div>
                          <div className="font-mono text-[10px] text-muted-foreground truncate max-w-[220px]" title={cid}>
                            {cid}
                          </div>
                        </td>
                        <td className="py-3.5 px-4">
                          <button
                            type="button"
                            className="text-left group focus:outline-none"
                            title={`Filter campaigns by ${c.owner_name}`}
                            onClick={() => setSelectedOwner(c.owner_uid)}
                          >
                            <div className="font-semibold text-foreground group-hover:text-primary transition-colors">
                              {c.owner_name || 'Organizer'}
                            </div>
                            {c.owner_email && (
                              <div className="text-[11px] text-muted-foreground truncate max-w-[220px]">
                                {c.owner_email}
                              </div>
                            )}
                          </button>
                        </td>
                        <td className="py-3.5 px-4">
                          {isGoogleForm ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
                              <Sparkles className="w-3 h-3" />
                              Google Forms
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                              <FileSpreadsheet className="w-3 h-3" />
                              Spreadsheet
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold capitalize ${
                              isCompleted
                                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                                : isDraft
                                ? 'bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border border-zinc-500/20'
                                : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
                            }`}
                          >
                            {isCompleted && <CheckCircle2 className="w-3 h-3" />}
                            {isDraft && <Clock className="w-3 h-3" />}
                            {c.status || 'draft'}
                          </span>
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-foreground">{c.sent_count}</span>
                            <span className="text-muted-foreground">/</span>
                            <span>{c.total_recipients}</span>
                            <span className="text-[10px] text-muted-foreground">sent</span>
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Link to={`/campaigns?tab=certificate_studio&id=${cid}`}>
                              <Button variant="ghost" size="sm" className="h-7 text-xs px-2 gap-1 text-primary hover:bg-primary/10">
                                <ExternalLink className="w-3.5 h-3.5" />
                                Studio
                              </Button>
                            </Link>
                            <Link to={`/campaigns?tab=email_distributor&id=${cid}`}>
                              <Button variant="ghost" size="sm" className="h-7 text-xs px-2 gap-1 text-primary hover:bg-primary/10">
                                <Mail className="w-3.5 h-3.5" />
                                Distributor
                              </Button>
                            </Link>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-xs px-2 gap-1 text-destructive hover:bg-destructive/10"
                              onClick={() =>
                                setCampaignToDelete({
                                  id: cid,
                                  campaign_id: cid,
                                  name: cname,
                                  campaign_name: cname,
                                  total_recipients: c.total_recipients,
                                  sent_count: c.sent_count,
                                })
                              }
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                              Delete
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Super Admin Delete Modal */}
      <DeleteCampaignDialog
        campaign={campaignToDelete}
        isOpen={!!campaignToDelete}
        onClose={() => setCampaignToDelete(null)}
        onDeleted={handleCampaignDeleted}
      />
    </div>
  )
}
