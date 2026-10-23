import { createContext, useContext, useReducer } from 'react'

const Ctx = createContext(null)

const init = {
  page:           'query',
  tables:         [],
  activeTable:    null,
  activeTables:   [],   // NEW — list of selected tables for JOIN
  tableInfo:      {},
  schemaList:     [],
  lastResult:     null,
  lastQuery:      null,
  history:        [],
  histStats:      null,
  sidebarOpen:    true,
  loading:        false,
  inputMode:      'text',
}

function reducer(state, action) {
  switch (action.type) {
    case 'SET_PAGE':          return { ...state, page: action.payload }
    case 'SET_TABLES':        return { ...state, tables: action.payload }
    case 'SET_ACTIVE_TABLE':  return { ...state, activeTable: action.payload }
    case 'SET_ACTIVE_TABLES': return { ...state, activeTables: action.payload }
    case 'SET_TABLE_INFO':    return { ...state, tableInfo: { ...state.tableInfo, ...action.payload } }
    case 'SET_SCHEMA':        return { ...state, schemaList: action.payload }
    case 'SET_RESULT':        return { ...state, lastResult: action.payload }
    case 'SET_QUERY':         return { ...state, lastQuery: action.payload }
    case 'SET_HISTORY':       return { ...state, history: action.payload }
    case 'SET_HIST_STATS':    return { ...state, histStats: action.payload }
    case 'SET_SIDEBAR':       return { ...state, sidebarOpen: action.payload }
    case 'SET_LOADING':       return { ...state, loading: action.payload }
    case 'SET_INPUT_MODE':    return { ...state, inputMode: action.payload }
    default: return state
  }
}

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, init)
  return <Ctx.Provider value={{ state, dispatch }}>{children}</Ctx.Provider>
}

export function useApp() {
  return useContext(Ctx)
}
