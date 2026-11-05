import { createTheme } from '@mui/material/styles'

export const LINK_COLOR = '#3d7edb'
export const GRID_LINE = '#e0e0e0'

export const theme = createTheme({
  palette: {
    primary: { main: '#2196f3' },
    error: { main: '#d32f2f' },
    background: { default: '#f0f0f0' },
    text: { primary: '#111', secondary: '#666' },
  },
  typography: {
    fontFamily: '"Lato", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: { fontSize: 24, fontWeight: 700 },
  },
  shape: { borderRadius: 4 },
  components: {
    MuiDialog: { styleOverrides: { paper: { borderRadius: 0 } } },
    MuiDrawer: { styleOverrides: { paper: { borderRadius: 0 } } },
  },
})
