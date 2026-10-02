import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  FolderOpen,
  Plus,
  ArrowRight,
  Mail,
  LayoutGrid,
  Users,
  CheckCircle2,
  Clock,
  Send,
  Loader2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Link } from 'react-router-dom'
import { CampaignEmailComposer } from '@/components/gmail/CampaignEmailComposer'
import { api } from '@/services/api'

interface Campaign {
  id: string
  campaign_id: string
  name: string
  campaign_name: string
  description?: string
  status: string
  total_recipients: number
  sent_count: number
  created_at?: string
}

export default function CampaignsPage() {
  const [activeTab, setActiveTab] = useState<'campaigns' | 'email_distributor'>('campaigns')
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>('')
  const [selectedCampaignName, setSelectedCampaignName] = useState<string>('')

  useEffect(() => {
    async function loadCampaigns() {
      try {
        setLoading(true)
        const data = await api.get<Campaign[]>('/api/campaigns')
        if (Array.isArray(data)) {
          setCampaigns(data)
          if (data.length > 0) {
            setSelectedCampaignId(data[0].id || data[0].campaign_id)
            setSelectedCampaignName(data[0].name || data[0].campaign_name)
          }
        }
      } catch (err) {
        console.warn('Could not load campaigns list:', err)
      } finally {
        setLoading(false)
      }
    }
    loadCampaigns()
  }, [])

  const handleOpenDistributor = (campaign: Campaign) => {
    setSelectedCampaignId(campaign.id || campaign.campaign_id)
    setSelectedCampaignName(campaign.name || campaign.campaign_name)
    setActiveTab('email_distributor')
  }

  return (
    <div className="page-container py-8 max-w-5xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}>
          <h1 className="section-title">Campaigns & Distribution</h1>
          <p className="section-description">Manage certificate campaigns and distribute via Gmail.</p>
        </motion.div>

        <div className="flex items-center gap-2">
          {/* View switcher */}
          <div className="flex rounded-lg border bg-muted/40 p-1 text-xs">
            <button
              onClick={() => setActiveTab('campaigns')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-colors ${
                activeTab === 'campaigns'
                  ? 'bg-background shadow-xs text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <LayoutGrid className="h-3.5 w-3.5" />
              Campaigns
            </button>
            <button
              onClick={() => setActiveTab('email_distributor')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-colors ${
                activeTab === 'email_distributor'
                  ? 'bg-background shadow-xs text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Mail className="h-3.5 w-3.5" />
              Email Distribution
            </button>
          </div>

          <Link to="/campaigns/new">
            <Button variant="gradient" size="sm" className="gap-2 text-xs">
              <Plus className="h-3.5 w-3.5" />
              New Campaign
            </Button>
          </Link>
        </div>
      </div>

      {activeTab === 'campaigns' ? (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          {loading ? (
            <div className="flex items-center justify-center py-20 text-muted-foreground gap-2">
              <Loader2 className="h-5 w-5 animate-spin" />
              Loading your campaigns...
            </div>
          ) : campaigns.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {campaigns.map((camp) => {
                const cId = camp.id || camp.campaign_id
                const cName = camp.name || camp.campaign_name
                return (
                  <Card key={cId} className="hover:border-primary/50 transition-all shadow-xs flex flex-col justify-between">
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between gap-2">
                        <CardTitle className="text-base font-semibold leading-tight">{cName}</CardTitle>
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize bg-primary/10 text-primary border border-primary/20">
                          {camp.status || 'draft'}
                        </span>
                      </div>
                      {camp.description && (
                        <CardDescription className="line-clamp-2 mt-1">{camp.description}</CardDescription>
                      )}
                    </CardHeader>
                    <CardContent className="pt-0 space-y-4">
                      <div className="flex items-center gap-4 text-xs text-muted-foreground border-y py-2.5">
                        <div className="flex items-center gap-1.5">
                          <Users className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>{camp.total_recipients || 0} Recipients</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                          <span>{camp.sent_count || 0} Sent</span>
                        </div>
                        {camp.created_at && (
                          <div className="flex items-center gap-1.5 ml-auto">
                            <Clock className="h-3.5 w-3.5" />
                            <span>{new Date(camp.created_at).toLocaleDateString()}</span>
                          </div>
                        )}
                      </div>

                      <div className="flex items-center justify-between gap-2">
                        <Button
                          variant="gradient"
                          size="sm"
                          className="w-full gap-2 text-xs"
                          onClick={() => handleOpenDistributor(camp)}
                        >
                          <Send className="h-3.5 w-3.5" />
                          Distribute with Gmail
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <FolderOpen className="h-5 w-5 text-primary" />
                  All Campaigns
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-4">
                    <FolderOpen className="h-8 w-8 text-primary" />
                  </div>
                  <h3 className="font-semibold text-lg mb-2">No campaigns yet</h3>
                  <p className="text-muted-foreground text-sm max-w-sm mb-6">
                    Campaigns let you group participants, design certificate templates, generate PDFs, and automatically distribute them through Gmail.
                  </p>
                  <div className="flex flex-wrap items-center gap-3">
                    <Link to="/campaigns/new">
                      <Button variant="gradient" className="gap-2">
                        Create Campaign
                        <ArrowRight className="h-4 w-4" />
                      </Button>
                    </Link>
                    <Button
                      variant="outline"
                      onClick={() => setActiveTab('email_distributor')}
                      className="gap-2"
                    >
                      <Mail className="h-4 w-4 text-primary" />
                      Open Email Distributor
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </motion.div>
      ) : (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <CampaignEmailComposer
            campaignId={selectedCampaignId || 'default_campaign'}
            campaignName={selectedCampaignName || 'Certificate Campaign'}
          />
        </motion.div>
      )}
    </div>
  )
}
