import { create } from 'zustand'

type UIStore = {
  collapsed: boolean
  setCollapsed: (v: boolean) => void
}

export const useUIStore = create<UIStore>((set) => ({
  collapsed: false,
  setCollapsed: (collapsed) => set({ collapsed }),
}))
