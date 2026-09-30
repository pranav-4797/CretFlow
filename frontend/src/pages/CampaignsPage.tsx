import { motion } from 'framer-motion'
import { FolderOpen, Plus, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Link } from 'react-router-dom'

export default function CampaignsPage() {
  return (
    <div className="page-container py-8">
      <div className="flex items-center justify-between mb-8">
        <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}>
          <h1 className="section-title">Campaigns</h1>
          <p className="section-description">Manage your certificate campaigns.</p>
        </motion.div>
        <Link to="/campaigns/new">
          <Button variant="gradient" className="gap-2">
            <Plus className="h-4 w-4" />
            New Campaign
          </Button>
        </Link>
      </div>

      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
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
              <p className="text-muted-foreground text-sm max-w-xs mb-6">
                Campaigns let you group participants, design a certificate template, generate PDFs, and send them via Gmail.
              </p>
              <Link to="/campaigns/new">
                <Button variant="gradient" className="gap-2">
                  Create Campaign
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
