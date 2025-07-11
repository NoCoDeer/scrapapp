import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { ProLayout } from '@ant-design/pro-layout'
import {
  DashboardOutlined,
  BugOutlined,
  MonitorOutlined,
  SettingOutlined,
  DatabaseOutlined,
  UserOutlined,
  LogoutOutlined,
} from '@ant-design/icons'

import Dashboard from './pages/Dashboard'
import SpiderManagement from './pages/SpiderManagement'
import TaskMonitor from './pages/TaskMonitor'
import DataManagement from './pages/DataManagement'
import Settings from './pages/Settings'
import Login from './pages/Login'
import { useAuthStore } from './stores/authStore'

const App: React.FC = () => {
  const { isAuthenticated, user, logout } = useAuthStore()

  if (!isAuthenticated) {
    return <Login />
  }

  const menuItems = [
    {
      path: '/dashboard',
      name: 'Дашборд',
      icon: <DashboardOutlined />,
    },
    {
      path: '/spiders',
      name: 'Управление пауками',
      icon: <BugOutlined />,
    },
    {
      path: '/tasks',
      name: 'Мониторинг задач',
      icon: <MonitorOutlined />,
    },
    {
      path: '/data',
      name: 'Управление данными',
      icon: <DatabaseOutlined />,
    },
    {
      path: '/settings',
      name: 'Настройки',
      icon: <SettingOutlined />,
    },
  ]

  return (
    <div className="admin-layout">
      <ProLayout
        title="Job Scraper Admin"
        logo="/logo.svg"
        layout="mix"
        navTheme="dark"
        primaryColor="#1890ff"
        fixSiderbar
        fixedHeader
        route={{
          routes: menuItems,
        }}
        menuItemRender={(item, dom) => (
          <a
            onClick={() => {
              window.location.pathname = item.path || '/'
            }}
          >
            {dom}
          </a>
        )}
        rightContentRender={() => (
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <span style={{ color: '#fff' }}>
              <UserOutlined /> {user?.email}
            </span>
            <a
              onClick={logout}
              style={{ color: '#fff', cursor: 'pointer' }}
            >
              <LogoutOutlined /> Выйти
            </a>
          </div>
        )}
        headerContentRender={() => (
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <h1 style={{ margin: 0, color: '#fff' }}>
              Панель управления Job Scraper
            </h1>
          </div>
        )}
      >
        <div className="admin-content">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/spiders" element={<SpiderManagement />} />
            <Route path="/tasks" element={<TaskMonitor />} />
            <Route path="/data" element={<DataManagement />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </div>
      </ProLayout>
    </div>
  )
}

export default App
