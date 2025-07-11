import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { Layout } from 'antd'
import { Helmet } from 'react-helmet-async'

import AppLayout from './components/Layout/AppLayout'
import Dashboard from './pages/Dashboard'
import JobsList from './pages/Jobs/JobsList'
import JobDetail from './pages/Jobs/JobDetail'
import CompaniesList from './pages/Companies/CompaniesList'
import CompanyDetail from './pages/Companies/CompanyDetail'
import Search from './pages/Search'
import Admin from './pages/Admin'

const App: React.FC = () => {
  return (
    <>
      <Helmet>
        <title>Job Scraper - Система скрапинга вакансий</title>
        <meta name="description" content="Система для скрапинга и анализа вакансий с различных сайтов" />
      </Helmet>
      
      <Layout style={{ minHeight: '100vh' }}>
        <AppLayout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/jobs" element={<JobsList />} />
            <Route path="/jobs/:id" element={<JobDetail />} />
            <Route path="/companies" element={<CompaniesList />} />
            <Route path="/companies/:id" element={<CompanyDetail />} />
            <Route path="/search" element={<Search />} />
            <Route path="/admin" element={<Admin />} />
          </Routes>
        </AppLayout>
      </Layout>
    </>
  )
}

export default App
