import { useState, useRef, useEffect, useCallback, PointerEvent as ReactPointerEvent } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plus,
  Trash2,
  Copy,
  Eye,
  EyeOff,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Layers,
  Move,
  ChevronDown,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { CertificateField, TemplateConfig } from '@/services/templates'

interface CanvaCertificateEditorProps {
  templateImageUrl: string
  config: TemplateConfig
  availableVariables?: string[]
  sampleData?: Record<string, string>
  onChange: (newConfig: TemplateConfig) => void
  onSave?: () => void
  isSaving?: boolean
}

const FONT_FAMILIES = [
  { id: 'PlayfairDisplay', name: 'Playfair Display', fontStyle: "'Playfair Display', serif", category: 'Luxury Serif' },
  { id: 'GreatVibes', name: 'Great Vibes', fontStyle: "'Great Vibes', cursive", category: 'Calligraphy Script' },
  { id: 'Cinzel', name: 'Cinzel', fontStyle: "'Cinzel', serif", category: 'Roman / Academic' },
  { id: 'Montserrat', name: 'Montserrat', fontStyle: "'Montserrat', sans-serif", category: 'Clean Sans' },
  { id: 'AlexBrush', name: 'Alex Brush', fontStyle: "'Alex Brush', cursive", category: 'Flowing Cursive' },
]

const COLOR_PRESETS = [
  { name: 'Dark Slate', hex: '#1e293b' },
  { name: 'Pure Obsidian', hex: '#0f172a' },
  { name: 'Luxury Gold', hex: '#b45309' },
  { name: 'Royal Navy', hex: '#1e3a8a' },
  { name: 'Deep Emerald', hex: '#065f46' },
  { name: 'Burgundy', hex: '#831843' },
  { name: 'Silver Gray', hex: '#64748b' },
  { name: 'Pure White', hex: '#ffffff' },
]

export function CanvaCertificateEditor({
  templateImageUrl,
  config,
  availableVariables = [],
  sampleData = {},
  onChange,
  onSave,
  isSaving = false,
}: CanvaCertificateEditorProps) {
  // Extract fields from config or normalize legacy config
  const initialFields = useCallback((): CertificateField[] => {
    if (config.fields && config.fields.length > 0) {
      return config.fields
    }
    // Fallback: convert legacy fields
    const legacyFields: CertificateField[] = [
      {
        id: 'field_name',
        label: 'Participant Name',
        variable_key: 'name',
        x_percent: config.name_x_percent ?? 50.0,
        y_percent: config.name_y_percent ?? 48.0,
        font_family: config.font_family || 'PlayfairDisplay',
        font_size: config.font_size || 64,
        font_color: config.font_color || '#1e293b',
        text_align: (config.text_align as 'center' | 'left' | 'right') || 'center',
        is_enabled: true,
        sample_value: sampleData.name || 'Rahul Sharma',
      },
    ]
    if (config.show_cert_id) {
      legacyFields.push({
        id: 'field_cert_id',
        label: 'Certificate ID',
        variable_key: 'certificate_id',
        x_percent: config.cert_id_x_percent ?? 88.0,
        y_percent: config.cert_id_y_percent ?? 92.0,
        font_family: 'Montserrat',
        font_size: Math.max(16, Math.floor((config.font_size || 64) * 0.25)),
        font_color: '#64748b',
        text_align: 'center',
        is_enabled: true,
        sample_value: sampleData.certificate_id || 'CERT-2026-001',
      })
    }
    if (config.show_date) {
      legacyFields.push({
        id: 'field_date',
        label: 'Issue Date',
        variable_key: 'date',
        x_percent: config.date_x_percent ?? 15.0,
        y_percent: config.date_y_percent ?? 92.0,
        font_family: 'Montserrat',
        font_size: Math.max(16, Math.floor((config.font_size || 64) * 0.25)),
        font_color: '#64748b',
        text_align: 'center',
        is_enabled: true,
        sample_value: sampleData.date || 'November 05, 2026',
      })
    }
    return legacyFields
  }, [config, sampleData])

  const [fields, setFields] = useState<CertificateField[]>(initialFields)
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(fields[0]?.id || null)
  const [showAddMenu, setShowAddMenu] = useState(false)
  const [showColorPicker, setShowColorPicker] = useState(false)
  const [customVariableInput, setCustomVariableInput] = useState('')
  const [showCustomInput, setShowCustomInput] = useState(false)
  const [isSnappingCenter, setIsSnappingCenter] = useState(false)
  const [naturalWidth, setNaturalWidth] = useState<number>(1600)
  const imgRef = useRef<HTMLImageElement>(null)

  useEffect(() => {
    if (imgRef.current && imgRef.current.naturalWidth > 100) {
      setNaturalWidth(imgRef.current.naturalWidth)
    }
  }, [templateImageUrl])

  // Dragging state
  const canvasRef = useRef<HTMLDivElement>(null)
  const draggingFieldIdRef = useRef<string | null>(null)
  const dragStartPos = useRef<{ x: number; y: number; fieldX: number; fieldY: number } | null>(null)

  // Synchronize internal fields with parent config
  useEffect(() => {
    setFields(initialFields())
  }, [config])

  const updateFields = (newFields: CertificateField[]) => {
    setFields(newFields)
    // Keep legacy single-name fields updated in parallel for full backwards compatibility
    const nameField = newFields.find((f) => f.variable_key === 'name')
    const updatedConfig: TemplateConfig = {
      ...config,
      fields: newFields,
      name_x_percent: nameField ? nameField.x_percent : config.name_x_percent,
      name_y_percent: nameField ? nameField.y_percent : config.name_y_percent,
      font_family: nameField ? nameField.font_family : config.font_family,
      font_size: nameField ? nameField.font_size : config.font_size,
      font_color: nameField ? nameField.font_color : config.font_color,
      text_align: nameField ? nameField.text_align : config.text_align,
    }
    onChange(updatedConfig)
  }

  const selectedField = fields.find((f) => f.id === selectedFieldId) || null

  const updateSelectedField = (updates: Partial<CertificateField>) => {
    if (!selectedFieldId) return
    const newFields = fields.map((f) => (f.id === selectedFieldId ? { ...f, ...updates } : f))
    updateFields(newFields)
  }

  // Add new field
  const handleAddField = (label: string, variableKey: string, sampleVal?: string) => {
    const id = `field_${variableKey}_${Date.now()}`
    const newField: CertificateField = {
      id,
      label,
      variable_key: variableKey.toLowerCase().trim(),
      x_percent: 50.0,
      y_percent: 50.0 + (fields.length * 5) % 35,
      font_family: 'PlayfairDisplay',
      font_size: variableKey === 'name' ? 56 : 32,
      font_color: '#1e293b',
      text_align: 'center',
      is_enabled: true,
      sample_value: sampleVal || `{{${variableKey}}}`,
    }
    const newFields = [...fields, newField]
    updateFields(newFields)
    setSelectedFieldId(id)
    setShowAddMenu(false)
    setShowCustomInput(false)
    setCustomVariableInput('')
  }

  // Duplicate selected field
  const handleDuplicate = (field: CertificateField) => {
    const id = `field_${field.variable_key}_${Date.now()}`
    const copy: CertificateField = {
      ...field,
      id,
      label: `${field.label} (Copy)`,
      y_percent: Math.min(95, field.y_percent + 4),
    }
    const newFields = [...fields, copy]
    updateFields(newFields)
    setSelectedFieldId(id)
  }

  // Delete selected field
  const handleDelete = (id: string) => {
    const newFields = fields.filter((f) => f.id !== id)
    updateFields(newFields)
    if (selectedFieldId === id) {
      setSelectedFieldId(newFields[0]?.id || null)
    }
  }

  // Pointer down on a field to start dragging
  const handlePointerDown = (e: ReactPointerEvent<HTMLDivElement>, field: CertificateField) => {
    e.stopPropagation()
    setSelectedFieldId(field.id)
    draggingFieldIdRef.current = field.id
    dragStartPos.current = {
      x: e.clientX,
      y: e.clientY,
      fieldX: field.x_percent,
      fieldY: field.y_percent,
    }

    const handlePointerMove = (moveEv: PointerEvent) => {
      if (!canvasRef.current || !dragStartPos.current || !draggingFieldIdRef.current) return
      const rect = canvasRef.current.getBoundingClientRect()
      const deltaX = ((moveEv.clientX - dragStartPos.current.x) / rect.width) * 100
      const deltaY = ((moveEv.clientY - dragStartPos.current.y) / rect.height) * 100

      let newX = Math.max(0, Math.min(100, dragStartPos.current.fieldX + deltaX))
      const newY = Math.max(0, Math.min(100, dragStartPos.current.fieldY + deltaY))

      // Snap to center guideline if within 1.5% of center (50%)
      if (Math.abs(newX - 50.0) < 1.5) {
        newX = 50.0
        setIsSnappingCenter(true)
      } else {
        setIsSnappingCenter(false)
      }

      setFields((prev) =>
        prev.map((f) =>
          f.id === draggingFieldIdRef.current
            ? { ...f, x_percent: Math.round(newX * 10) / 10, y_percent: Math.round(newY * 10) / 10 }
            : f
        )
      )
    }

    const handlePointerUp = () => {
      setIsSnappingCenter(false)
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', handlePointerUp)
      setFields((currentFields) => {
        updateFields(currentFields)
        return currentFields
      })
      draggingFieldIdRef.current = null
      dragStartPos.current = null
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
  }

  // Helper for sample text preview
  const getDisplayText = (field: CertificateField): string => {
    const key = field.variable_key.toLowerCase().trim()
    if (sampleData[key]) return sampleData[key]
    if (field.sample_value) return field.sample_value
    if (key === 'name') return 'Rahul Sharma'
    if (key === 'college') return 'MIT Academy of Engineering'
    if (key === 'rank') return '1st Place Winner'
    if (key === 'certificate_id') return 'CERT-2026-001'
    if (key === 'date') return 'November 05, 2026'
    if (key === 'event_name') return 'Technical Workshop 2026'
    return `{{${key}}}`
  }

  // CSS font helper
  const getCssFontFamily = (familyId: string) => {
    const matched = FONT_FAMILIES.find((f) => f.id === familyId)
    return matched ? matched.fontStyle : "'Playfair Display', serif"
  }

  // Collect custom spreadsheet columns to offer
  const detectedCustomColumns = availableVariables.filter(
    (col) => !['name', 'email', 'certificate_id', 'date'].includes(col.toLowerCase())
  )

  return (
    <div className="space-y-4">
      {/* Canva Top Floating Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl border bg-card/95 shadow-sm backdrop-blur">
        {/* Left: Add Dynamic Field Dropdown */}
        <div className="relative">
          <Button
            type="button"
            variant="gradient"
            size="sm"
            onClick={() => setShowAddMenu(!showAddMenu)}
            className="gap-1.5 text-xs h-8 shadow-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Dynamic Field
            <ChevronDown className="h-3 w-3 opacity-70" />
          </Button>

          <AnimatePresence>
            {showAddMenu && (
              <motion.div
                initial={{ opacity: 0, y: 4, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 4, scale: 0.98 }}
                className="absolute left-0 top-10 z-50 w-64 p-2 rounded-xl border bg-card shadow-xl space-y-1.5"
              >
                <div className="px-2 py-1 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Standard Variables
                </div>
                <button
                  type="button"
                  onClick={() => handleAddField('Participant Name', 'name', 'Rahul Sharma')}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs hover:bg-primary/10 hover:text-primary transition-colors flex items-center justify-between"
                >
                  <span>👤 Student / Recipient Name</span>
                  <code className="text-[10px] text-muted-foreground">{'{{name}}'}</code>
                </button>
                <button
                  type="button"
                  onClick={() => handleAddField('College / Organization', 'college', 'MIT Academy of Engineering')}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs hover:bg-primary/10 hover:text-primary transition-colors flex items-center justify-between"
                >
                  <span>🏛️ College / Institute</span>
                  <code className="text-[10px] text-muted-foreground">{'{{college}}'}</code>
                </button>
                <button
                  type="button"
                  onClick={() => handleAddField('Award / Rank', 'rank', '1st Place')}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs hover:bg-primary/10 hover:text-primary transition-colors flex items-center justify-between"
                >
                  <span>🏆 Rank / Position</span>
                  <code className="text-[10px] text-muted-foreground">{'{{rank}}'}</code>
                </button>
                <button
                  type="button"
                  onClick={() => handleAddField('Event / Course Title', 'event_name', 'Research Paper Writing')}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs hover:bg-primary/10 hover:text-primary transition-colors flex items-center justify-between"
                >
                  <span>🎓 Event / Course Name</span>
                  <code className="text-[10px] text-muted-foreground">{'{{event_name}}'}</code>
                </button>
                <button
                  type="button"
                  onClick={() => handleAddField('Issue Date', 'date', 'November 05, 2026')}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs hover:bg-primary/10 hover:text-primary transition-colors flex items-center justify-between"
                >
                  <span>📅 Issue Date</span>
                  <code className="text-[10px] text-muted-foreground">{'{{date}}'}</code>
                </button>
                <button
                  type="button"
                  onClick={() => handleAddField('Certificate ID', 'certificate_id', 'CERT-2026-001')}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs hover:bg-primary/10 hover:text-primary transition-colors flex items-center justify-between"
                >
                  <span>🆔 Certificate ID</span>
                  <code className="text-[10px] text-muted-foreground">{'{{certificate_id}}'}</code>
                </button>

                {/* Detected Spreadsheet Columns */}
                {detectedCustomColumns.length > 0 && (
                  <>
                    <div className="pt-1.5 border-t px-2 py-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
                      From Uploaded Excel
                    </div>
                    {detectedCustomColumns.map((col) => (
                      <button
                        key={col}
                        type="button"
                        onClick={() => handleAddField(col.replace(/_/g, ' ').toUpperCase(), col)}
                        className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs hover:bg-emerald-50 dark:hover:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 transition-colors flex items-center justify-between"
                      >
                        <span className="capitalize">{col.replace(/_/g, ' ')}</span>
                        <code className="text-[10px]">{`{{${col}}}`}</code>
                      </button>
                    ))}
                  </>
                )}

                {/* Custom variable option */}
                <div className="pt-1 border-t">
                  {showCustomInput ? (
                    <div className="p-1.5 space-y-2">
                      <Input
                        placeholder="e.g. department, score"
                        value={customVariableInput}
                        onChange={(e) => setCustomVariableInput(e.target.value)}
                        className="h-7 text-xs font-mono"
                        autoFocus
                      />
                      <div className="flex items-center gap-1.5">
                        <Button
                          size="sm"
                          variant="default"
                          className="h-6 text-[11px] px-2 w-full"
                          disabled={!customVariableInput.trim()}
                          onClick={() =>
                            handleAddField(
                              customVariableInput.trim().toUpperCase(),
                              customVariableInput.trim()
                            )
                          }
                        >
                          Add Field
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setShowCustomInput(true)}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs text-primary font-medium hover:bg-primary/10 transition-colors"
                    >
                      + Custom Field...
                    </button>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Middle: Active Field Inspector */}
        {selectedField ? (
          <div className="flex flex-wrap items-center gap-2">
            {/* Font family */}
            <select
              value={selectedField.font_family}
              onChange={(e) => updateSelectedField({ font_family: e.target.value })}
              className="h-8 text-xs bg-background border rounded-lg px-2.5 focus:outline-none focus:ring-1 focus:ring-primary max-w-[140px]"
            >
              {FONT_FAMILIES.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>

            {/* Font size */}
            <div className="flex items-center border rounded-lg overflow-hidden h-8 bg-background">
              <button
                type="button"
                title="Decrease font size"
                onClick={() => {
                  const step = selectedField.font_size <= 16 ? 2 : 4
                  updateSelectedField({ font_size: Math.max(2, selectedField.font_size - step) })
                }}
                className="px-2.5 hover:bg-muted text-xs text-muted-foreground font-semibold h-full transition-colors cursor-pointer"
              >
                -
              </button>
              <div className="flex items-center px-1">
                <input
                  type="number"
                  min={2}
                  max={250}
                  value={selectedField.font_size}
                  onChange={(e) => {
                    const val = parseInt(e.target.value, 10)
                    if (!isNaN(val)) {
                      updateSelectedField({ font_size: Math.max(2, Math.min(250, val)) })
                    }
                  }}
                  className="w-10 text-center text-xs font-mono font-medium bg-transparent border-none focus:outline-hidden py-0 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  title="Click to type custom font size (down to 2pt)"
                />
                <span className="text-[10px] text-muted-foreground font-medium select-none pr-0.5">pt</span>
              </div>
              <button
                type="button"
                title="Increase font size"
                onClick={() => {
                  const step = selectedField.font_size < 16 ? 2 : 4
                  updateSelectedField({ font_size: Math.min(250, selectedField.font_size + step) })
                }}
                className="px-2.5 hover:bg-muted text-xs text-muted-foreground font-semibold h-full transition-colors cursor-pointer"
              >
                +
              </button>
            </div>

            {/* Color Swatch / Picker Popover */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowColorPicker(!showColorPicker)}
                className="h-8 px-2 rounded-lg border bg-background flex items-center gap-1.5 text-xs hover:border-primary transition-colors"
              >
                <div
                  className="h-4 w-4 rounded-full border shadow-2xs"
                  style={{ backgroundColor: selectedField.font_color }}
                />
                <span className="font-mono text-[11px]">{selectedField.font_color}</span>
              </button>

              <AnimatePresence>
                {showColorPicker && (
                  <motion.div
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 4 }}
                    className="absolute left-0 top-10 z-50 p-3 rounded-xl border bg-card shadow-xl space-y-2 w-48"
                  >
                    <div className="text-[11px] font-semibold text-muted-foreground">Color Presets</div>
                    <div className="grid grid-cols-4 gap-1.5">
                      {COLOR_PRESETS.map((swatch) => (
                        <button
                          key={swatch.hex}
                          type="button"
                          title={swatch.name}
                          onClick={() => {
                            updateSelectedField({ font_color: swatch.hex })
                            setShowColorPicker(false)
                          }}
                          className={`h-7 w-7 rounded-lg border transition-transform ${
                            selectedField.font_color.toLowerCase() === swatch.hex.toLowerCase()
                              ? 'scale-110 ring-2 ring-primary ring-offset-1'
                              : 'hover:scale-105'
                          }`}
                          style={{ backgroundColor: swatch.hex }}
                        />
                      ))}
                    </div>
                    <div className="pt-2 border-t flex items-center gap-2">
                      <input
                        type="color"
                        value={selectedField.font_color}
                        onChange={(e) => updateSelectedField({ font_color: e.target.value })}
                        className="h-7 w-7 rounded cursor-pointer p-0.5 border"
                      />
                      <Input
                        value={selectedField.font_color}
                        onChange={(e) => updateSelectedField({ font_color: e.target.value })}
                        className="h-7 text-xs font-mono"
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Alignment Buttons */}
            <div className="flex items-center border rounded-lg bg-background p-0.5">
              <button
                type="button"
                onClick={() => updateSelectedField({ text_align: 'left' })}
                className={`p-1.5 rounded-md ${
                  selectedField.text_align === 'left' ? 'bg-primary/10 text-primary font-bold' : 'text-muted-foreground hover:text-foreground'
                }`}
                title="Align Left"
              >
                <AlignLeft className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => updateSelectedField({ text_align: 'center' })}
                className={`p-1.5 rounded-md ${
                  selectedField.text_align === 'center' ? 'bg-primary/10 text-primary font-bold' : 'text-muted-foreground hover:text-foreground'
                }`}
                title="Align Center"
              >
                <AlignCenter className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => updateSelectedField({ text_align: 'right' })}
                className={`p-1.5 rounded-md ${
                  selectedField.text_align === 'right' ? 'bg-primary/10 text-primary font-bold' : 'text-muted-foreground hover:text-foreground'
                }`}
                title="Align Right"
              >
                <AlignRight className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Duplicate & Delete */}
            <button
              type="button"
              onClick={() => handleDuplicate(selectedField)}
              className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg border hover:bg-muted"
              title="Duplicate Field"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => handleDelete(selectedField.id)}
              className="p-1.5 text-muted-foreground hover:text-red-600 rounded-lg border hover:bg-red-50 dark:hover:bg-red-950/40"
              title="Delete Field"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
          <div className="text-xs text-muted-foreground italic flex items-center gap-1.5">
            <Move className="h-3.5 w-3.5" />
            Click any field on the certificate to edit typography and position
          </div>
        )}

        {/* Right: Save Design Button */}
        {onSave && (
          <Button
            type="button"
            variant="default"
            size="sm"
            onClick={onSave}
            disabled={isSaving}
            className="gap-1.5 text-xs h-8 bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs ml-auto"
          >
            {isSaving ? 'Saving...' : 'Save Design'}
          </Button>
        )}
      </div>

      {/* Canva Interactive Drag-and-Drop Canvas Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 items-start">
        {/* Main Certificate Canvas (3 Columns) */}
        <div className="lg:col-span-3">
          <div
            ref={canvasRef}
            onClick={() => {
              setShowAddMenu(false)
              setShowColorPicker(false)
            }}
            className="relative w-full rounded-xl border border-border/80 shadow-md overflow-hidden select-none bg-zinc-900 group cursor-default [container-type:inline-size]"
            style={{ touchAction: 'none', containerType: 'inline-size' }}
          >
            {/* Background Template Image */}
            <img
              ref={imgRef}
              src={templateImageUrl}
              alt="Certificate Template"
              className="w-full h-auto block pointer-events-none"
              onLoad={(e) => {
                if (e.currentTarget.naturalWidth > 100) {
                  setNaturalWidth(e.currentTarget.naturalWidth)
                }
              }}
            />

            {/* Vertical Center Guideline (Snaps at 50%) */}
            {isSnappingCenter && (
              <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-0.5 bg-blue-500 z-30 pointer-events-none shadow-xs" />
            )}

            {/* Dynamic Placed Text Layers */}
            {fields
              .filter((f) => f.is_enabled)
              .map((field) => {
                const isSelected = selectedFieldId === field.id
                const displayText = getDisplayText(field)

                return (
                  <div
                    key={field.id}
                    onPointerDown={(e) => handlePointerDown(e, field)}
                    className={`absolute cursor-move transition-shadow z-20 group/field ${
                      isSelected
                        ? 'ring-2 ring-primary ring-offset-2 ring-offset-background/40 bg-primary/10 rounded-xs'
                        : 'hover:ring-1 hover:ring-primary/60 rounded-xs'
                    }`}
                    style={{
                      left: `${field.x_percent}%`,
                      top: `${field.y_percent}%`,
                      transform:
                        field.text_align === 'left'
                          ? 'translate(0, -50%)'
                          : field.text_align === 'right'
                          ? 'translate(-100%, -50%)'
                          : 'translate(-50%, -50%)',
                      fontFamily: getCssFontFamily(field.font_family),
                      fontSize: `clamp(2px, ${(field.font_size / (naturalWidth > 100 ? naturalWidth : 1600)) * 100}cqw, 140px)`,
                      color: field.font_color,
                      textAlign: field.text_align,
                      whiteSpace: 'nowrap',
                      padding: '2px 8px',
                    }}
                  >
                    {/* Rendered Text */}
                    <span>{displayText}</span>

                    {/* Active Drag Handles & Badge */}
                    {isSelected && (
                      <>
                        <span className="absolute -top-5 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground text-[9px] font-sans font-bold px-1.5 py-0.5 rounded shadow-xs uppercase tracking-wider pointer-events-none">
                          {field.label} ({field.x_percent}%, {field.y_percent}%)
                        </span>
                        {/* Drag indicator icon */}
                        <span className="absolute -right-2 -bottom-2 bg-primary text-primary-foreground rounded-full p-0.5 shadow-xs pointer-events-none">
                          <Move className="h-2.5 w-2.5" />
                        </span>
                      </>
                    )}
                  </div>
                )
              })}
          </div>

          <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1.5 px-1">
            <span>💡 Click and drag any text box directly on the certificate to move it.</span>
            <span>Blue line indicates exact horizontal center (50%).</span>
          </div>
        </div>

        {/* Right Sidebar: Layers & Variable Inspector (1 Column) */}
        <div className="space-y-3">
          <div className="p-3.5 rounded-xl border bg-card shadow-xs space-y-3">
            <div className="flex items-center justify-between border-b pb-2">
              <span className="text-xs font-semibold flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-primary" />
                Certificate Layers ({fields.length})
              </span>
            </div>

            <div className="space-y-1.5 max-h-[360px] overflow-y-auto">
              {fields.map((f) => (
                <div
                  key={f.id}
                  onClick={() => setSelectedFieldId(f.id)}
                  className={`p-2 rounded-lg text-xs border transition-colors flex items-center justify-between cursor-pointer ${
                    selectedFieldId === f.id
                      ? 'border-primary bg-primary/5 text-primary font-medium'
                      : 'border-border/60 hover:bg-muted/40 text-foreground'
                  }`}
                >
                  <div className="space-y-0.5 truncate pr-2">
                    <div className="font-semibold text-[11px] truncate">{f.label}</div>
                    <div className="text-[10px] text-muted-foreground font-mono">
                      {`{{${f.variable_key}}}`} • X:{f.x_percent}% Y:{f.y_percent}%
                    </div>
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        const updated = fields.map((x) =>
                          x.id === f.id ? { ...x, is_enabled: !x.is_enabled } : x
                        )
                        updateFields(updated)
                      }}
                      className="text-muted-foreground hover:text-foreground p-1"
                      title={f.is_enabled ? 'Hide on certificate' : 'Show on certificate'}
                    >
                      {f.is_enabled ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3 text-red-400" />}
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDelete(f.id)
                      }}
                      className="text-muted-foreground hover:text-red-600 p-1"
                      title="Delete field"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Selected Field Quick Coordinate Sliders */}
            {selectedField && (
              <div className="pt-2 border-t space-y-2">
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground">X Coordinate</span>
                    <span className="font-mono font-semibold">{selectedField.x_percent}%</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="95"
                    step="0.5"
                    value={selectedField.x_percent}
                    onChange={(e) => updateSelectedField({ x_percent: parseFloat(e.target.value) })}
                    className="w-full h-1 bg-muted rounded appearance-none cursor-pointer"
                  />
                </div>

                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground">Y Coordinate</span>
                    <span className="font-mono font-semibold">{selectedField.y_percent}%</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="95"
                    step="0.5"
                    value={selectedField.y_percent}
                    onChange={(e) => updateSelectedField({ y_percent: parseFloat(e.target.value) })}
                    className="w-full h-1 bg-muted rounded appearance-none cursor-pointer"
                  />
                </div>

                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground">Font Size</span>
                    <span className="font-mono font-semibold">{selectedField.font_size}pt</span>
                  </div>
                  <input
                    type="range"
                    min="2"
                    max="140"
                    step="1"
                    value={selectedField.font_size}
                    onChange={(e) => updateSelectedField({ font_size: parseInt(e.target.value, 10) })}
                    className="w-full h-1 bg-muted rounded appearance-none cursor-pointer"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
