import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import { router } from './router'
import './styles/global.css'
import './styles/tokens.css'
import './styles/t02.css'
import './styles/design-v2.css'
import './styles/ui01.css'
import './styles/ui011.css'
import './styles/ui012.css'
import './styles/ui013.css'
import './styles/ui02.css'
import './styles/ui022.css'
import './styles/ui023.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider theme={{ algorithm: theme.darkAlgorithm, token: { colorPrimary: '#2e8cff', colorBgBase: '#07111f', colorTextBase:'#eaf4ff', borderRadius: 12, fontFamily: 'Inter, "PingFang SC", "Microsoft YaHei", sans-serif' } }}>
      <RouterProvider router={router}/>
    </ConfigProvider>
  </React.StrictMode>
)
