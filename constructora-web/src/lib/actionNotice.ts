export type ActionNoticeKind = 'success' | 'info' | 'warning' | 'error'

export type ActionNoticePayload = {
  message: string
  kind?: ActionNoticeKind
}

export const ACTION_NOTICE_EVENT = 'acsm:action-notice'

export function showActionNotice(message: string, kind: ActionNoticeKind = 'success') {
  window.dispatchEvent(
    new CustomEvent<ActionNoticePayload>(ACTION_NOTICE_EVENT, {
      detail: { message, kind },
    }),
  )
}
