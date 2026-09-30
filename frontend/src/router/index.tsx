import { createBrowserRouter } from 'react-router-dom'
import AppLayout from '../layouts/AppLayout'
import HomePage from '../pages/HomePage'
import RadarPage from '../pages/RadarPage'
import MarketsPage from '../pages/MarketsPage'
import CompaniesPage from '../pages/CompaniesPage'
import CompanyDetailPage from '../pages/CompanyDetailPage'
import SignalsPage from '../pages/SignalsPage'
import OpportunitiesPage from '../pages/OpportunitiesPage'
import ExperimentsPage from '../pages/ExperimentsPage'
import SourcesPage from '../pages/SourcesPage'
import JobsPage from '../pages/JobsPage'
import LogsPage from '../pages/LogsPage'
import SettingsPage from '../pages/SettingsPage'

export const router = createBrowserRouter([{ path:'/', element:<AppLayout/>, children:[
  { index:true, element:<HomePage/> },
  { path:'radar', element:<RadarPage/> },
  { path:'markets', element:<MarketsPage/> },
  { path:'companies', element:<CompaniesPage/> },
  { path:'companies/:id', element:<CompanyDetailPage/> },
  { path:'signals', element:<SignalsPage/> },
  { path:'opportunities', element:<OpportunitiesPage/> },
  { path:'experiments', element:<ExperimentsPage/> },
  { path:'sources', element:<SourcesPage/> },
  { path:'jobs', element:<JobsPage/> },
  { path:'logs', element:<LogsPage/> },
  { path:'settings', element:<SettingsPage/> },
]}])
