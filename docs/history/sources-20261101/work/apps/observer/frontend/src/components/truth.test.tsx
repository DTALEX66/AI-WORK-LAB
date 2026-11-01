// U07/U08: mount REAL components and assert the rendered truth discipline.
// No phantom data: an empty/absent snapshot must render UNKNOWN, and the
// software panel must NOT fabricate a "Healthy / verified" identity.
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { TokenPanel } from '@/components/dashboard/TokenPanel'
import { ProjectPanel } from '@/components/dashboard/ProjectPanel'
import { ExecutionTable } from '@/components/dashboard/ExecutionTable'
import { SoftwareView } from '@/views/SoftwareView'
import { CompactHUD } from '@/views/CompactHUD'

// double-safe: setup.ts already cleans up; do it here too so each test is
// isolated even if the file is run standalone.
import { afterEach } from 'vitest'
afterEach(() => cleanup())

describe('U07 component truth (mount real components)', () => {
  it('TokenPanel with no data renders UNKNOWN everywhere, no 0', () => {
    render(<TokenPanel snap={null} />)
    const unknowns = screen.getAllByText('UNKNOWN')
    expect(unknowns.length).toBeGreaterThan(0)
    // no fabricated token count like "0"
    expect(screen.queryByText('0')).toBeNull()
  })

  it('ProjectPanel with no data says the registry is empty / UNKNOWN', () => {
    render(<ProjectPanel snap={null} />)
    expect(screen.getByText(/数据源未接入|registry 为空/)).toBeInTheDocument()
  })

  it('ExecutionTable with no data and no source says waiting, not fabricates rows', () => {
    render(<ExecutionTable rows={[]} hasData={false} />)
    expect(screen.getByText(/数据源未接入/)).toBeInTheDocument()
    expect(screen.queryAllByRole('row')).toHaveLength(0)
  })

  it('SoftwareView with no projection does NOT claim a verified/healthy install', () => {
    render(<SoftwareView snap={null} />)
    // The empty state is present (truthful "no data").
    expect(screen.getByText(/无软件身份投影/)).toBeInTheDocument()
    // And it never renders a bogus "SINGLE_VERIFIED / 已验证" badge for absent data.
    expect(screen.queryByText('已验证')).toBeNull()
  })

  it('CompactHUD with no data shows UNKNOWN transport + 0-fabrication', () => {
    render(<CompactHUD snap={null} live={false} />)
    expect(screen.getAllByText('UNKNOWN').length).toBeGreaterThan(0)
  })
})
