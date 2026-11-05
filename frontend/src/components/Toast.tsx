import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined'
import { Alert, AlertTitle, Button, Snackbar } from '@mui/material'
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

export interface ToastOptions {
  title: string
  description?: string
  severity?: 'success' | 'info' | 'warning' | 'error'
  actionLabel?: string
  onAction?: () => void
}

const ToastContext = createContext<{ notify: (options: ToastOptions) => void }>({ notify: () => {} })
export const useToast = () => useContext(ToastContext)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<(ToastOptions & { key: number }) | null>(null)
  const [open, setOpen] = useState(false)

  const notify = useCallback((options: ToastOptions) => {
    setToast({ ...options, key: Date.now() })
    setOpen(true)
  }, [])
  const value = useMemo(() => ({ notify }), [notify])
  const severity = toast?.severity ?? 'success'

  return (
    <ToastContext.Provider value={value}>
      {children}
      <Snackbar
        key={toast?.key}
        open={open}
        autoHideDuration={severity === 'success' || severity === 'info' ? 5000 : 9000}
        onClose={(_, reason) => reason !== 'clickaway' && setOpen(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          severity={severity}
          icon={severity === 'success' ? <CheckCircleOutlined /> : undefined}
          onClose={() => setOpen(false)}
          action={
            toast?.actionLabel ? (
              <Button
                color="inherit"
                size="small"
                onClick={() => {
                  setOpen(false)
                  toast.onAction?.()
                }}
              >
                {toast.actionLabel}
              </Button>
            ) : undefined
          }
          sx={{ minWidth: 280, maxWidth: 420, alignItems: 'center' }}
        >
          <AlertTitle sx={{ mb: toast?.description ? 0.25 : 0 }}>{toast?.title}</AlertTitle>
          {toast?.description}
        </Alert>
      </Snackbar>
    </ToastContext.Provider>
  )
}
