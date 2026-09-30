import { motion } from 'framer-motion'
import { Shield, CheckCircle2, XCircle, Loader2, Award } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'

// Demo certificate data for the landing page link
const DEMO_CERT = {
  certificateId: 'CERT-2026-000001',
  participantName: 'Jane Doe',
  eventName: 'Annual Innovation Summit 2026',
  organization: 'TechCorp Institute',
  issueDate: '2026-09-30',
  status: 'generated',
}

export default function VerifyPage() {
  const { certificateId } = useParams<{ certificateId: string }>()
  const [loading, setLoading] = useState(true)
  const [cert, setCert] = useState<typeof DEMO_CERT | null>(null)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    // Simulate API call
    setTimeout(() => {
      if (certificateId === 'demo' || certificateId === DEMO_CERT.certificateId) {
        setCert(DEMO_CERT)
      } else {
        setNotFound(true)
      }
      setLoading(false)
    }, 1000)
  }, [certificateId])

  return (
    <div className="min-h-screen flex flex-col bg-muted/30">
      {/* Header */}
      <header className="border-b border-border bg-background/80 backdrop-blur-xl py-4 px-6 flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl certflow-gradient">
          <Award className="h-4 w-4 text-white" />
        </div>
        <span className="font-bold text-lg">CertFlow</span>
        <span className="text-muted-foreground text-sm ml-2">· Certificate Verification</span>
      </header>

      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-lg">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
            <div className="text-center mb-8">
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 mb-3">
                <Shield className="h-6 w-6 text-primary" />
              </div>
              <h1 className="text-2xl font-bold mb-1">Certificate Verification</h1>
              <p className="text-muted-foreground text-sm">
                Verifying: <code className="font-mono text-foreground bg-muted px-1.5 py-0.5 rounded">{certificateId}</code>
              </p>
            </div>

            <Card className="overflow-hidden">
              <CardContent className="p-0">
                {loading ? (
                  <div className="flex flex-col items-center justify-center py-16 gap-4">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <p className="text-sm text-muted-foreground">Verifying certificate...</p>
                  </div>
                ) : notFound ? (
                  <div className="flex flex-col items-center justify-center py-16 gap-4">
                    <div className="flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10">
                      <XCircle className="h-7 w-7 text-destructive" />
                    </div>
                    <div className="text-center">
                      <h3 className="font-semibold text-lg mb-1">Certificate Not Found</h3>
                      <p className="text-muted-foreground text-sm max-w-xs">
                        No certificate with ID <strong>{certificateId}</strong> exists in our records.
                      </p>
                    </div>
                  </div>
                ) : cert ? (
                  <>
                    {/* Valid certificate */}
                    <div className="certflow-gradient p-6 text-white text-center">
                      <CheckCircle2 className="h-10 w-10 mx-auto mb-2 opacity-90" />
                      <div className="font-bold text-lg">Certificate Verified</div>
                      <div className="text-white/70 text-sm mt-1">This certificate is authentic and valid.</div>
                    </div>
                    <div className="p-6 space-y-4">
                      {[
                        { label: 'Certificate ID', value: cert.certificateId, mono: true },
                        { label: 'Participant', value: cert.participantName },
                        { label: 'Event', value: cert.eventName },
                        { label: 'Issued by', value: cert.organization },
                        { label: 'Issue Date', value: new Date(cert.issueDate).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) },
                      ].map((row) => (
                        <div key={row.label} className="flex items-start justify-between gap-4 py-2 border-b border-border last:border-0">
                          <span className="text-sm text-muted-foreground flex-shrink-0">{row.label}</span>
                          <span className={`text-sm font-medium text-right ${row.mono ? 'font-mono' : ''}`}>
                            {row.value}
                          </span>
                        </div>
                      ))}
                    </div>
                  </>
                ) : null}
              </CardContent>
            </Card>

            <p className="text-center text-xs text-muted-foreground mt-4">
              Powered by CertFlow · Secure certificate verification
            </p>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
