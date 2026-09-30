import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Award,
  Shield,
  ArrowRight,
  CheckCircle2,
  Zap,
  FileSpreadsheet,
  Mail,
  BarChart3,
  Lock,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

const features = [
  {
    icon: FileSpreadsheet,
    title: 'Smart Excel Import',
    description:
      'Upload XLSX, XLS, or CSV files. Auto-detect Name and Email columns with manual mapping fallback.',
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
  },
  {
    icon: Award,
    title: 'Visual Certificate Editor',
    description:
      'Drag, resize, and style dynamic fields on your certificate template with real-time preview.',
    color: 'text-violet-500',
    bg: 'bg-violet-500/10',
  },
  {
    icon: Zap,
    title: 'Bulk Generation',
    description:
      'Generate hundreds of personalized certificates in the background without blocking your work.',
    color: 'text-amber-500',
    bg: 'bg-amber-500/10',
  },
  {
    icon: Mail,
    title: 'Gmail Integration',
    description:
      'Connect your Gmail via OAuth 2.0. Send personalized certificates automatically — no passwords stored.',
    color: 'text-blue-500',
    bg: 'bg-blue-500/10',
  },
  {
    icon: BarChart3,
    title: 'Distribution Reports',
    description:
      'Track every email: sent, failed, retried. Export detailed reports as CSV or Excel.',
    color: 'text-pink-500',
    bg: 'bg-pink-500/10',
  },
  {
    icon: Shield,
    title: 'Certificate Verification',
    description:
      'Every certificate gets a unique ID. Share a public verification link for instant validation.',
    color: 'text-cyan-500',
    bg: 'bg-cyan-500/10',
  },
]

const steps = [
  { step: '01', title: 'Upload Participants', description: 'Import your Excel/CSV with names and emails.' },
  { step: '02', title: 'Design Certificate', description: 'Upload your template and position the name, date, and other fields.' },
  { step: '03', title: 'Generate & Send', description: 'Bulk-generate certificates and distribute via Gmail in one click.' },
  { step: '04', title: 'Track & Verify', description: 'Monitor delivery, retry failures, and provide certificate verification.' },
]

const stats = [
  { label: 'Certificates Generated', value: '500K+' },
  { label: 'Emails Delivered', value: '99.2%' },
  { label: 'Organizations', value: '1,200+' },
  { label: 'Time Saved', value: '10x' },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-border/40 bg-background/80 backdrop-blur-xl">
        <div className="page-container flex h-16 items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl certflow-gradient">
              <Award className="h-4.5 w-4.5 text-white" />
            </div>
            <span className="text-lg font-bold tracking-tight">CertFlow</span>
          </Link>
          <div className="flex items-center gap-3">
            <Link to="/login">
              <Button variant="ghost" size="sm">Sign In</Button>
            </Link>
            <Link to="/signup">
              <Button size="sm" variant="gradient">
                Get Started Free
              </Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-32 pb-20 lg:pt-40 lg:pb-32">
        {/* Background gradients */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] rounded-full bg-primary/5 blur-3xl" />
          <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-violet-500/5 blur-3xl" />
          <div className="absolute top-1/3 left-0 w-[300px] h-[300px] rounded-full bg-emerald-500/5 blur-3xl" />
        </div>

        {/* Dot grid */}
        <div
          className="absolute inset-0 -z-10 opacity-[0.03]"
          style={{
            backgroundImage: 'radial-gradient(circle, hsl(246 80% 60%) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }}
        />

        <div className="page-container text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm font-medium text-primary mb-6">
              <Zap className="h-3.5 w-3.5" />
              Certificate generation, automated distribution
            </div>

            <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight text-foreground mb-6 text-balance">
              Generate &amp; Send{' '}
              <span className="certflow-gradient-text">Certificates</span>
              <br />
              at Scale
            </h1>

            <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10 text-balance">
              CertFlow automates your entire certificate workflow — from Excel import to
              personalized PDF generation and Gmail distribution, with real-time tracking
              and public verification.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link to="/signup">
                <Button size="xl" variant="gradient" className="shadow-glow gap-2">
                  Start for Free
                  <ArrowRight className="h-5 w-5" />
                </Button>
              </Link>
              <Link to="/verify/demo">
                <Button size="xl" variant="outline" className="gap-2">
                  <Shield className="h-4 w-4" />
                  View Verification
                </Button>
              </Link>
            </div>
          </motion.div>

          {/* Stats row */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-8 max-w-3xl mx-auto"
          >
            {stats.map((stat) => (
              <div key={stat.label} className="text-center">
                <div className="text-3xl font-bold certflow-gradient-text">{stat.value}</div>
                <div className="text-sm text-muted-foreground mt-1">{stat.label}</div>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-20 lg:py-28 border-t border-border/50">
        <div className="page-container">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-4">
              Everything you need to run
              <br />
              <span className="certflow-gradient-text">certificate campaigns</span>
            </h2>
            <p className="text-muted-foreground text-lg max-w-xl mx-auto">
              A complete platform for event organizers, educators, and HR teams.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.07 }}
                className="group rounded-2xl border border-border bg-card p-6 hover:border-primary/30 hover:shadow-card-hover transition-all duration-300"
              >
                <div className={`inline-flex h-11 w-11 items-center justify-center rounded-xl ${feature.bg} mb-4`}>
                  <feature.icon className={`h-5 w-5 ${feature.color}`} />
                </div>
                <h3 className="font-semibold text-lg mb-2">{feature.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How it Works */}
      <section className="py-20 lg:py-28 bg-muted/30 border-y border-border/50">
        <div className="page-container">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-4">
              From spreadsheet to inbox
              <br />
              <span className="certflow-gradient-text">in 4 simple steps</span>
            </h2>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {steps.map((step, i) => (
              <motion.div
                key={step.step}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="relative"
              >
                {i < steps.length - 1 && (
                  <div className="hidden lg:block absolute top-5 left-full w-full h-px bg-gradient-to-r from-border to-transparent z-0" />
                )}
                <div className="relative z-10">
                  <div className="text-4xl font-bold certflow-gradient-text mb-3 font-mono">{step.step}</div>
                  <h3 className="font-semibold text-lg mb-2">{step.title}</h3>
                  <p className="text-sm text-muted-foreground">{step.description}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 lg:py-28">
        <div className="page-container">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="relative overflow-hidden rounded-3xl certflow-gradient p-12 text-center text-white"
          >
            <div className="absolute inset-0 opacity-10"
              style={{
                backgroundImage: 'radial-gradient(circle, white 1px, transparent 1px)',
                backgroundSize: '30px 30px',
              }}
            />
            <div className="relative z-10">
              <Award className="h-12 w-12 mx-auto mb-4 opacity-90" />
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Ready to streamline your certificate workflow?
              </h2>
              <p className="text-white/80 text-lg mb-8 max-w-xl mx-auto">
                Join thousands of organizers who automate certificate generation and distribution with CertFlow.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link to="/signup">
                  <Button size="xl" className="bg-white text-primary hover:bg-white/90 gap-2 shadow-lg">
                    Get Started Free
                    <ArrowRight className="h-5 w-5" />
                  </Button>
                </Link>
              </div>
              <div className="mt-6 flex items-center justify-center gap-6 text-sm text-white/70">
                {['No credit card required', 'Free to start', 'Cancel anytime'].map((item) => (
                  <div key={item} className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-10">
        <div className="page-container flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-lg certflow-gradient">
              <Award className="h-3.5 w-3.5 text-white" />
            </div>
            <span className="font-semibold text-foreground">CertFlow</span>
            <span>· Certificate Generation Platform</span>
          </div>
          <div className="flex items-center gap-1">
            <Lock className="h-3.5 w-3.5" />
            <span>Secured with Firebase &amp; OAuth 2.0</span>
          </div>
          <div>
            <Link to="/verify/demo" className="hover:text-foreground transition-colors">
              Certificate Verification
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
