import React from 'react'
import { Card, Table, Tag, Button, Space, Typography, Progress, Statistic, Row, Col } from 'antd'
import { 
  ClockCircleOutlined, 
  CheckCircleOutlined, 
  ExclamationCircleOutlined,
  ReloadOutlined,
  StopOutlined
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from 'react-query'

const { Title, Text } = Typography

interface Task {
  id: string
  name: string
  status: 'pending' | 'running' | 'success' | 'failure' | 'retry'
  progress: number
  startTime: string
  endTime?: string
  duration?: number
  result?: any
  error?: string
  worker: string
}

interface TaskStats {
  total: number
  pending: number
  running: number
  success: number
  failure: number
}

const TaskMonitor: React.FC = () => {
  const queryClient = useQueryClient()

  // Получение списка задач
  const { data: tasks, isLoading } = useQuery<Task[]>(
    'tasks',
    async () => {
      const response = await fetch('/api/admin/tasks')
      return response.json()
    },
    { refetchInterval: 5000 }
  )

  // Получение статистики задач
  const { data: stats } = useQuery<TaskStats>(
    'task-stats',
    async () => {
      const response = await fetch('/api/admin/task-stats')
      return response.json()
    },
    { refetchInterval: 10000 }
  )

  // Мутация для отмены задачи
  const cancelTaskMutation = useMutation(
    async (taskId: string) => {
      const response = await fetch(`/api/admin/tasks/${taskId}/cancel`, {
        method: 'POST'
      })
      if (!response.ok) throw new Error('Failed to cancel task')
      return response.json()
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('tasks')
      }
    }
  )

  // Колонки таблицы задач
  const taskColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 100,
      render: (id: string) => (
        <Text code style={{ fontSize: 11 }}>
          {id.substring(0, 8)}...
        </Text>
      )
    },
    {
      title: 'Название',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => <Text strong>{name}</Text>
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusConfig = {
          pending: { color: 'default', text: 'Ожидание', icon: <ClockCircleOutlined /> },
          running: { color: 'blue', text: 'Выполняется', icon: <ClockCircleOutlined /> },
          success: { color: 'green', text: 'Успешно', icon: <CheckCircleOutlined /> },
          failure: { color: 'red', text: 'Ошибка', icon: <ExclamationCircleOutlined /> },
          retry: { color: 'orange', text: 'Повтор', icon: <ReloadOutlined /> }
        }
        const config = statusConfig[status as keyof typeof statusConfig]
        return (
          <Tag color={config.color} icon={config.icon}>
            {config.text}
          </Tag>
        )
      }
    },
    {
      title: 'Прогресс',
      dataIndex: 'progress',
      key: 'progress',
      width: 120,
      render: (progress: number, record: Task) => (
        record.status === 'running' ? (
          <Progress percent={progress} size="small" />
        ) : (
          <span>-</span>
        )
      )
    },
    {
      title: 'Воркер',
      dataIndex: 'worker',
      key: 'worker',
      width: 120
    },
    {
      title: 'Время начала',
      dataIndex: 'startTime',
      key: 'startTime',
      width: 150,
      render: (time: string) => new Date(time).toLocaleString('ru-RU')
    },
    {
      title: 'Длительность',
      key: 'duration',
      width: 100,
      render: (record: Task) => {
        if (record.status === 'running') {
          const duration = Date.now() - new Date(record.startTime).getTime()
          return `${Math.floor(duration / 1000)}с`
        }
        if (record.duration) {
          return `${Math.floor(record.duration / 1000)}с`
        }
        return '-'
      }
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 100,
      render: (record: Task) => (
        <Space>
          {(record.status === 'pending' || record.status === 'running') && (
            <Button
              size="small"
              danger
              icon={<StopOutlined />}
              onClick={() => cancelTaskMutation.mutate(record.id)}
              loading={cancelTaskMutation.isLoading}
            >
              Отменить
            </Button>
          )}
        </Space>
      )
    }
  ]

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>Мониторинг задач</Title>
        <Text type="secondary">Отслеживание выполнения задач Celery</Text>
      </div>

      {/* Статистика задач */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={4}>
          <Card>
            <Statistic
              title="Всего"
              value={stats?.total || 0}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={4}>
          <Card>
            <Statistic
              title="Ожидание"
              value={stats?.pending || 0}
              valueStyle={{ color: '#666' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={4}>
          <Card>
            <Statistic
              title="Выполняется"
              value={stats?.running || 0}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={4}>
          <Card>
            <Statistic
              title="Успешно"
              value={stats?.success || 0}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={4}>
          <Card>
            <Statistic
              title="Ошибки"
              value={stats?.failure || 0}
              valueStyle={{ color: '#ff4d4f' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={4}>
          <Card>
            <Statistic
              title="Успешность"
              value={stats ? Math.round((stats.success / stats.total) * 100) : 0}
              suffix="%"
              valueStyle={{ 
                color: stats && (stats.success / stats.total) > 0.8 ? '#52c41a' : '#ff4d4f' 
              }}
            />
          </Card>
        </Col>
      </Row>

      {/* Таблица задач */}
      <Card
        title="Список задач"
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              queryClient.invalidateQueries('tasks')
              queryClient.invalidateQueries('task-stats')
            }}
          >
            Обновить
          </Button>
        }
      >
        <Table
          dataSource={tasks}
          columns={taskColumns}
          loading={isLoading}
          rowKey="id"
          pagination={{ 
            pageSize: 20,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => 
              `${range[0]}-${range[1]} из ${total} задач`
          }}
          size="small"
          className="admin-table"
          expandable={{
            expandedRowRender: (record: Task) => (
              <div style={{ padding: 16, background: '#fafafa' }}>
                {record.error && (
                  <div style={{ marginBottom: 16 }}>
                    <Text strong style={{ color: '#ff4d4f' }}>Ошибка:</Text>
                    <pre style={{ 
                      background: '#fff2f0', 
                      padding: 8, 
                      borderRadius: 4,
                      fontSize: 12,
                      marginTop: 8,
                      whiteSpace: 'pre-wrap'
                    }}>
                      {record.error}
                    </pre>
                  </div>
                )}
                {record.result && (
                  <div>
                    <Text strong>Результат:</Text>
                    <pre style={{ 
                      background: '#f6ffed', 
                      padding: 8, 
                      borderRadius: 4,
                      fontSize: 12,
                      marginTop: 8,
                      whiteSpace: 'pre-wrap'
                    }}>
                      {JSON.stringify(record.result, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ),
            rowExpandable: (record: Task) => !!(record.error || record.result)
          }}
        />
      </Card>
    </div>
  )
}

export default TaskMonitor
