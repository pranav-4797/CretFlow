import { useState } from 'react'
import { motion } from 'framer-motion'
import { FolderOpen, Plus, ArrowRight, Mail, LayoutGrid } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Link } from 'react-router-dom'
import { CampaignEmailComposer } from '@/components/gmail/CampaignEmailComposer'

export default function CampaignsPage() {
  const [activeTab, setActiveTab] = useState<'campaigns' | 'email_distributor'>('campaigns')
  const [selectedCampaignId] = useState('demo-campaign-001')

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
        </motion.div>
      ) : (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <CampaignEmailComposer
            campaignId={selectedCampaignId}
            campaignName="Annual Certificate Campaign"
          />
        </motion.div>
      )}
    </div>
  )
}
