// WUI-11 · the eight states must stay eight, and the two the snapshot cannot answer must stay named.
import { describe, it, expect } from 'vitest'

import {
  NON_PROJECTABLE_STATES, STATE_DEFINITIONS, STATE_BY_ID, snapshotStateOf,
} from './stateVocabulary'
import { mkSnap, mkProject } from '@/test/snapshotFixture'
import type { SnapshotV3 } from '@/types'

describe('state vocabulary (WUI-11)', () => {
  it('carries the eight required states, each with a unique id and label', () => {
    expect(STATE_DEFINITIONS).toHaveLength(8)
    const ids = STATE_DEFINITIONS.map((definition) => definition.id)
    expect(new Set(ids).size).toBe(8)
    expect(new Set(STATE_DEFINITIONS.map((definition) => definition.label)).size).toBe(8)
    expect(ids.sort()).toEqual([
      'delayed', 'hidden-by-policy', 'insufficient-permission', 'no-data', 'not-connected',
      'not-existing', 'partial-failure', 'unsupported',
    ])
  })

  it('every state says what it asserts, what it is based on and what to do next', () => {
    for (const definition of STATE_DEFINITIONS) {
      expect(definition.meaning.trim().length, definition.id).toBeGreaterThan(4)
      expect(definition.signal.trim().length, definition.id).toBeGreaterThan(4)
      expect(definition.nextAction.trim().length, definition.id).toBeGreaterThan(4)
    }
  })

  it('names exactly the two states the shipped snapshot cannot answer', () => {
    expect(NON_PROJECTABLE_STATES.sort()).toEqual(['hidden-by-policy', 'insufficient-permission'])
  })

  describe('snapshotStateOf keeps the three "nothing to show" answers apart', () => {
    it('no snapshot and no failure is unknown, not offline and not empty', () => {
      expect(snapshotStateOf(null, null)).toBe('unknown')
    })

    it('a failed read is not-connected', () => {
      expect(snapshotStateOf(null, 'snapshot fetch refused')).toBe('not-connected')
    })

    it('an OFFLINE transport word is not-connected even when a stale snapshot is on screen', () => {
      const snap = mkSnap({ transport: { ...mkSnap({}).transport, transportState: 'OFFLINE' } })
      expect(snapshotStateOf(snap, null)).toBe('not-connected')
    })

    it('a delayed or stale snapshot is delayed, never 无数据', () => {
      const delayed = mkSnap({ transport: { ...mkSnap({}).transport, transportState: 'DELAYED' } })
      expect(snapshotStateOf(delayed, null)).toBe('delayed')
      const stale = mkSnap({ transport: { ...mkSnap({}).transport, transportState: 'LIVE', freshnessState: 'STALE' } })
      expect(snapshotStateOf(stale, null)).toBe('delayed')
    })

    it('a short coverage numerator is a partial failure, not an empty projection', () => {
      const snap = mkSnap({
        projects: [mkProject()],
        coverage: { numerator: 3, denominator: 7, scope: 'adapters' },
      })
      expect(snapshotStateOf(snap, null)).toBe('partial-failure')
    })

    it('a queried-and-empty project set is no-data', () => {
      // coverage is pinned full here because the shared fixture carries a deliberate 3/4 shortfall: a
      // partial-coverage snapshot is a partial failure FIRST, and that ordering is the product rule.
      expect(snapshotStateOf(mkSnap({
        projects: [],
        coverage: { numerator: 4, denominator: 4, scope: 'collectors' },
      }), null)).toBe('no-data')
    })

    it('a healthy snapshot with data is NOT reported as a state at all', () => {
      // The collapse this prevents: a page that answers "无数据" over real rows is indistinguishable
      // from one that is genuinely empty, and the reader stops believing either.
      const snap = mkSnap({
        projects: [mkProject()],
        coverage: { numerator: 4, denominator: 4, scope: 'collectors' },
      })
      expect(snapshotStateOf(snap, null)).toBe('unknown')
    })

    it('a null coverage denominator is not treated as a failure', () => {
      const snap = mkSnap({
        projects: [mkProject()],
        coverage: { numerator: 0, denominator: null, scope: null },
      })
      expect(snapshotStateOf(snap, null)).toBe('unknown')
    })
  })

  it('STATE_BY_ID resolves every definition and nothing else', () => {
    for (const definition of STATE_DEFINITIONS) {
      expect(STATE_BY_ID[definition.id]).toBe(definition)
    }
    expect(STATE_BY_ID['everything-is-fine' as never]).toBeUndefined()
  })
})
