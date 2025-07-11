import React, { useEffect, useState } from 'react'
import { Row, Col, Card, Statistic, Progress, Table, Tag, Button, Space, Typography } from 'antd'
import { 
  BugOutlined, 
  DatabaseOutlined, 
  ClockCircleOutlined, 
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { useQuery } from 'react-query'

const { Title, Text } = Typography

interface DashboardStats {
  totalJobs: number
  totalCompanies: number
  activeTasks: number
  completedTasks: number
  errorTasks: number
  spiderStatus: {
    [key: string]: 'running' | 'stopped' | 'error'
  }
}

interface RecentJob {
  id: string
  title: string
  company: string
  location: string
  createdAt: string
  status: 'new' | 'processed' | 'error'
}

const Dashboard: React.FC = () => {
  const [realTimeLogs, setRealTimeLogs] = useState<string[]>([])

  // Получение статистики
  const { data: stats, isLoading: statsLoading, refetch: refetchStats } = useQuery<DashboardStats>(
    'dashboard-stats',
    async () => {
      const response = await fetch('/api/admin/stats')
      return response.json()
    },
    { refetchInterval: 30000 } // Обновление каждые 30 секунд
  )

  // Получение последних вакансий
  const { data: recentJobs, isLoading: jobsLoading } = useQuery<RecentJob[]>(
    'recent-jobs',
    async () => {
      const response = await fetch('/api/admin/recent-jobs')
      return response.json()
    },
    { refetchInterval: 60000 } // Обновление каждую минуту
  )

  // WebSocket для real-time логов
  useEffect(() => {
    const ws = new WebSocket(`ws://${window.location.host}/ws/logs`)
    
    ws.onmessage = (event) => {
      const logEntry = JSON.parse(event.data)
      setRealTimeLogs(prev => [...prev.slice(-99), logEntry.message]) // Последние 100 записей
    }

    return () => ws.close()
  }, [])

  // Конфигурация графика активности
  const activityChartOption = {
    title: {
      text: 'Активность парсинга за последние 24 часа',
      left: 'center'
    },
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: Array.from({ length: 24 }, (_, i) => `${i}:00`)
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: 'Обработано вакансий',
        type: 'line',
        data: Array.from({ length: 24 }, () => Math.floor(Math.random() * 100)),
        smooth: true,
        areaStyle: {}
      }
    ]
  }

  // Колонки таблицы последних вакансий
  const jobColumns = [
    {
      title: 'Название',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: 'Компания',
      dataIndex: 'company',
      key: 'company',
    },
    {
      title: 'Локация',
      dataIndex: 'location',
      key: 'location',
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusConfig = {
          new: { color: 'blue', text: 'Новая' },
          processed: { color: 'green', text: 'Обработана' },
          error: { color: 'red', text: 'Ошибка' }
        }
        const config = statusConfig[status as keyof typeof statusConfig]
        return <Tag color={config.color}>{config.text}</Tag>
      }
    },
    {
      title: 'Дата',
      dataIndex: 'createdAt',
      key: 'createdAt',
      render: (date: string) => new Date(date).toLocaleString('ru-RU')
    }
  ]

  const handleSpiderAction = async (spiderName: string, action: 'start' | 'stop') => {
    try {
      await fetch(`/api/admin/spiders/${spiderName}/${action}`, {
        method: 'POST'
      })
      refetchStats()
    } catch (error) {
      console.error('Spider action error:', error)
    }
  }

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>Дашборд</Title>
        <Text type="secondary">Обзор системы парсинга вакансий</Text>
      </div>

      {/* Статистические карточки */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="dashboard-card">
            <Statistic
              title="Всего вакансий"
              value={stats?.totalJobs || 0}
              prefix={<DatabaseOutlined />}
              loading={statsLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="dashboard-card">
            <Statistic
              title="Компаний"
              value={stats?.totalCompanies || 0}
              prefix={<BugOutlined />}
              loading={statsLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="dashboard-card">
            <Statistic
              title="Активные задачи"
              value={stats?.activeTasks || 0}
              prefix={<ClockCircleOutlined />}
              loading={statsLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="dashboard-card">
            <Statistic
              title="Завершенные задачи"
              value={stats?.completedTasks || 0}
              prefix={<CheckCircleOutlined />}
              loading={statsLoading}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {/* Статус пауков */}
        <Col xs={24} lg={8}>
          <Card 
            title="Статус пауков" 
            className="dashboard-card"
            extra={
              <Button 
                icon={<ReloadOutlined />} 
                onClick={() => refetchStats()}
                size="small"
              >
                Обновить
              </Button>
            }
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              {stats?.spiderStatus && Object.entries(stats.spiderStatus).map(([name, status]) => (
                <div key={name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <Text strong>{name}</Text>
                    <br />
                    <Tag 
                      color={status === 'running' ? 'green' : status === 'error' ? 'red' : 'default'}
                      className={`spider-status-${status}`}
                    >
                      {status === 'running' ? 'Работает' : status === 'error' ? 'Ошибка' : 'Остановлен'}
                    </Tag>
                  </div>
                  <Space>
                    <Button
                      size="small"
                      type={status === 'running' ? 'default' : 'primary'}
                      icon={status === 'running' ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                      onClick={() => handleSpiderAction(name, status === 'running' ? 'stop' : 'start')}
                    >
                      {status === 'running' ? 'Стоп' : 'Старт'}
                    </Button>
                  </Space>
                </div>
              ))}
            </Space>
          </Card>
        </Col>

        {/* График активности */}
        <Col xs={24} lg={16}>
          <Card title="График активности" className="dashboard-card">
            <ReactECharts option={activityChartOption} style={{ height: 300 }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        {/* Последние вакансии */}
        <Col xs={24} lg={14}>
          <Card title="Последние вакансии" className="dashboard-card">
            <Table
              dataSource={recentJobs}
              columns={jobColumns}
              loading={jobsLoading}
              pagination={{ pageSize: 10 }}
              size="small"
              className="admin-table"
            />
          </Card>
        </Col>

        {/* Real-time логи */}
        <Col xs={24} lg={10}>
          <Card title="Логи в реальном времени" className="dashboard-card">
            <div className="real-time-logs">
              {realTimeLogs.length === 0 ? (
                <div style={{ textAlign: 'center', color: '#666' }}>
                  Ожидание логов...
                </div>
              ) : (
                realTimeLogs.map((log, index) => (
                  <div key={index} className="log-entry">
                    {log}
                  </div>
                ))
              )}
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default Dashboard
