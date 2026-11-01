// WUI-14 · the IME composition guard.
//
// The 20261009 interaction rule is 中文IME组合阶段不误触快捷键. Before this helper existed no keydown
// handler in the app checked composition state, and two of them did damage when a Chinese input method
// confirmed a candidate: the global `Ctrl/Cmd+K` handler fired on the key event the IME was still
// owning, and the command palette's `Enter` handler RAN the highlighted item while the user was only
// accepting a word. Both look like a working shortcut until someone types in Chinese.
//
// `keyCode === 229` is kept alongside `isComposing` because that is what browsers report for a key event
// that belongs to an in-progress composition, including the ones where `isComposing` is false on the very
// first keystroke of the session.
export interface MaybeComposing {
  isComposing?: boolean
  keyCode?: number
  nativeEvent?: { isComposing?: boolean; keyCode?: number }
}

export function isImeComposing(event: MaybeComposing | null | undefined): boolean {
  if (!event) return false
  const native = event.nativeEvent
  const composing = event.isComposing ?? native?.isComposing
  const keyCode = event.keyCode ?? native?.keyCode
  return composing === true || keyCode === 229
}
