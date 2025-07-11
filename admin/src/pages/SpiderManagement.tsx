import React, { useState } from 'react'
import { Card, Table, Button, Space, Tag, Modal, Form, Input, Select, message, Typography, Tabs } from 'antd'
import { 
  PlayCircleOutlined, 
  PauseCircleOutlined, 
  SettingOutlined, 
  DeleteOutlined,
  PlusOutlined,
  EditOutlined,
  BugOutlined
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from 'react-query'

const { Title, Text } = Typography
const { TabPane } = Tabs

interface Spider {
  id: string
  name: string
  displayName: string
  status: 'running' | 'stopped' | 'error'
  lastRun: string
  totalJobs: number
  errorCount: number
  settings: {
    delay: number
    concurrent: number
    enabled: boolean
  }
}

interface SpiderLog {
  id: string
  spiderName: string
  level: 'info' | 'warning' | 'error'
  message: string
  timestamp: string
}

const SpiderManagement: React.FC = () => {
  const [selectedSpider, setSelectedSpider] = useState<Spider | null>(null)
  const [isModalVisible, setIsModalVisible] = useState(false)
  const [isEditMode, setIsEditMode] = useState(false)
  const [form] = Form.useForm()
  const queryClient = useQueryClient()

  // Получение списка пауков
  const { data: spiders, isLoading } = useQuery<Spider[]>(
    'spiders',
    async () => {
      const response = await fetch('/api/admin/spiders')
      return response.json()
    },
    { refetchInterval: 10000 }
  )

  // Получение логов пауков
  const { data: logs } = useQuery<SpiderLog[]>(
    'spider-logs',
    async () => {
      const response = await fetch('/api/admin/spider-logs')
      return response.json()
    },
    { refetchInterval: 5000 }
  )

  // Мутация для управления пауками
  const spiderActionMutation = useMutation(
    async ({ spiderName, action }: { spiderName: string; action: 'start' | 'stop' | 'restart' }) => {
      const response = await fetch(`/api/admin/spiders/${spiderName}/${action}`, {
        method: 'POST'
      })
      if (!response.ok) throw new Error('Failed to perform action')
      return response.json()
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('spiders')
        message.success('Действие выполнено успешно')
      },
      onError: () => {
        message.error('Ошибка при выполнении действия')
      }
    }
  )

  // Мутация для сохранения настроек паука
  const saveSpiderMutation = useMutation(
    async (spider: Partial<Spider>) => {
      const response = await fetch(`/api/admin/spiders/${spider.id || 'new'}`, {
        method: spider.id ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(spider)
      })
      if (!response.ok) throw new Error('Failed to save spider')
      return response.json()
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('spiders')
        setIsModalVisible(false)
        form.resetFields()
        message.success('Паук сохранен успешно')
      },
      onError: () => {
        message.error('Ошибка при сохранении паука')
      }
    }
  )

  // Колонки таблицы пауков
  const spiderColumns = [
    {
      title: 'Название',
      dataIndex: 'displayName',
      key: 'displayName',
      render: (text: string, record: Spider) => (
        <Space>
          <BugOutlined />
          <div>
            <div style={{ fontWeight: 'bold' }}>{text}</div>
            <Text type="secondary" style={{ fontSize: 12 }}>{record.name}</Text>
          </div>
        </Space>
      )
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusConfig = {
          running: { color: 'green', text: 'Работает' },
          stopped: { color: 'default', text: 'Остановлен' },
          error: { color: 'red', text: 'Ошибка' }
        }
        const config = statusConfig[status as keyof typeof statusConfig]
        return <Tag color={config.color}>{config.text}</Tag>
      }
    },
    {
      title: 'Последний запуск',
      dataIndex: 'lastRun',
      key: 'lastRun',
      render: (date: string) => date ? new Date(date).toLocaleString('ru-RU') : 'Никогда'
    },
    {
      title: 'Вакансий',
      dataIndex: 'totalJobs',
      key: 'totalJobs',
      render: (count: number) => count.toLocaleString()
    },
    {
      title: 'Ошибки',
      dataIndex: 'errorCount',
      key: 'errorCount',
      render: (count: number) => (
        <Tag color={count > 0 ? 'red' : 'green'}>
          {count}
        </Tag>
      )
    },
    {
      title: 'Действия',
      key: 'actions',
      render: (record: Spider) => (
        <Space>
          <Button
            size="small"
            type={record.status === 'running' ? 'default' : 'primary'}
            icon={record.status === 'running' ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
            onClick={() => spiderActionMutation.mutate({
              spiderName: record.name,
              action: record.status === 'running' ? 'stop' : 'start'
            })}
            loading={spiderActionMutation.isLoading}
          >
            {record.status === 'running' ? 'Стоп' : 'Старт'}
          </Button>
          <Button
            size="small"
            icon={<SettingOutlined />}
            onClick={() => {
              setSelectedSpider(record)
              setIsEditMode(true)
              setIsModalVisible(true)
              form.setFieldsValue(record)
            }}
          >
            Настройки
          </Button>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => {
              Modal.confirm({
                title: 'Удалить паука?',
                content: `Вы уверены, что хотите удалить паука "${record.displayName}"?`,
                onOk: () => {
                  // TODO: Implement delete
                }
              })
            }}
          >
            Удалить
          </Button>
        </Space>
      )
    }
  ]

  // Колонки таблицы логов
  const logColumns = [
    {
      title: 'Время',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 150,
      render: (date: string) => new Date(date).toLocaleString('ru-RU')
    },
    {
      title: 'Паук',
      dataIndex: 'spiderName',
      key: 'spiderName',
      width: 120
    },
    {
      title: 'Уровень',
      dataIndex: 'level',
      key: 'level',
      width: 100,
      render: (level: string) => {
        const levelConfig = {
          info: { color: 'blue', text: 'Инфо' },
          warning: { color: 'orange', text: 'Предупреждение' },
          error: { color: 'red', text: 'Ошибка' }
        }
        const config = levelConfig[level as keyof typeof levelConfig]
        return <Tag color={config.color}>{config.text}</Tag>
      }
    },
    {
      title: 'Сообщение',
      dataIndex: 'message',
      key: 'message',
      ellipsis: true
    }
  ]

  const handleSaveSpider = (values: any) => {
    const spiderData = {
      ...values,
      id: isEditMode ? selectedSpider?.id : undefined
    }
    saveSpiderMutation.mutate(spiderData)
  }

  const handleAddSpider = () => {
    setSelectedSpider(null)
    setIsEditMode(false)
    setIsModalVisible(true)
    form.resetFields()
  }

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>Управление пауками</Title>
        <Text type="secondary">Настройка и мониторинг пауков для парсинга</Text>
      </div>

      <Tabs defaultActiveKey="spiders">
        <TabPane tab="Пауки" key="spiders">
          <Card
            title="Список пауков"
            extra={
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleAddSpider}
              >
                Добавить паука
              </Button>
            }
          >
            <Table
              dataSource={spiders}
              columns={spiderColumns}
              loading={isLoading}
              rowKey="id"
              pagination={{ pageSize: 10 }}
              className="admin-table"
            />
          </Card>
        </TabPane>

        <TabPane tab="Логи" key="logs">
          <Card title="Логи пауков">
            <Table
              dataSource={logs}
              columns={logColumns}
              rowKey="id"
              pagination={{ pageSize: 20 }}
              size="small"
              className="admin-table"
            />
          </Card>
        </TabPane>
      </Tabs>

      {/* Модальное окно настроек паука */}
      <Modal
        title={isEditMode ? 'Редактировать паука' : 'Добавить паука'}
        open={isModalVisible}
        onCancel={() => {
          setIsModalVisible(false)
          form.resetFields()
        }}
        footer={null}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSaveSpider}
          className="admin-form"
        >
          <Form.Item
            name="name"
            label="Системное имя"
            rules={[{ required: true, message: 'Введите системное имя' }]}
          >
            <Input placeholder="site1_spider" disabled={isEditMode} />
          </Form.Item>

          <Form.Item
            name="displayName"
            label="Отображаемое имя"
            rules={[{ required: true, message: 'Введите отображаемое имя' }]}
          >
            <Input placeholder="Паук для Site1.com" />
          </Form.Item>

          <Form.Item
            name={['settings', 'delay']}
            label="Задержка между запросами (сек)"
            rules={[{ required: true, message: 'Введите задержку' }]}
          >
            <Input type="number" min={1} max={60} />
          </Form.Item>

          <Form.Item
            name={['settings', 'concurrent']}
            label="Количество одновременных запросов"
            rules={[{ required: true, message: 'Введите количество' }]}
          >
            <Input type="number" min={1} max={10} />
          </Form.Item>

          <Form.Item
            name={['settings', 'enabled']}
            label="Статус"
            rules={[{ required: true, message: 'Выберите статус' }]}
          >
            <Select>
              <Select.Option value={true}>Включен</Select.Option>
              <Select.Option value={false}>Отключен</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item>
            <Space>
              <Button
                type="primary"
                htmlType="submit"
                loading={saveSpiderMutation.isLoading}
              >
                Сохранить
              </Button>
              <Button
                onClick={() => {
                  setIsModalVisible(false)
                  form.resetFields()
                }}
              >
                Отмена
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default SpiderManagement
