import React, { useState } from 'react'
import { Card, Form, Input, Button, Switch, Select, InputNumber, Typography, Space, message, Tabs, Divider } from 'antd'
import { SaveOutlined, ReloadOutlined, TestOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from 'react-query'

const { Title, Text } = Typography
const { TextArea } = Input
const { TabPane } = Tabs

interface Settings {
  general: {
    siteName: string
    adminEmail: string
    timezone: string
    language: string
  }
  scraping: {
    defaultDelay: number
    maxConcurrent: number
    retryAttempts: number
    timeout: number
    userAgents: string[]
    proxies: string[]
  }
  notifications: {
    emailEnabled: boolean
    slackEnabled: boolean
    slackWebhook: string
    errorThreshold: number
  }
  database: {
    cleanupEnabled: boolean
    cleanupDays: number
    backupEnabled: boolean
    backupSchedule: string
  }
}

const Settings: React.FC = () => {
  const [form] = Form.useForm()
  const [activeTab, setActiveTab] = useState('general')
  const queryClient = useQueryClient()

  // Получение настроек
  const { data: settings, isLoading } = useQuery<Settings>(
    'settings',
    async () => {
      const response = await fetch('/api/admin/settings')
      return response.json()
    }
  )

  // Мутация для сохранения настроек
  const saveSettingsMutation = useMutation(
    async (values: Partial<Settings>) => {
      const response = await fetch('/api/admin/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values)
      })
      if (!response.ok) throw new Error('Failed to save settings')
      return response.json()
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('settings')
        message.success('Настройки сохранены успешно')
      },
      onError: () => {
        message.error('Ошибка при сохранении настроек')
      }
    }
  )

  // Мутация для тестирования настроек
  const testSettingsMutation = useMutation(
    async (type: 'email' | 'slack' | 'database') => {
      const response = await fetch(`/api/admin/test/${type}`, {
        method: 'POST'
      })
      if (!response.ok) throw new Error('Test failed')
      return response.json()
    },
    {
      onSuccess: (data, type) => {
        message.success(`Тест ${type} прошел успешно`)
      },
      onError: (error, type) => {
        message.error(`Ошибка при тестировании ${type}`)
      }
    }
  )

  const handleSave = (values: any) => {
    saveSettingsMutation.mutate(values)
  }

  const handleReset = () => {
    form.setFieldsValue(settings)
    message.info('Настройки сброшены к сохраненным значениям')
  }

  React.useEffect(() => {
    if (settings) {
      form.setFieldsValue(settings)
    }
  }, [settings, form])

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>Настройки системы</Title>
        <Text type="secondary">Конфигурация параметров системы парсинга</Text>
      </div>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        className="admin-form"
      >
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          {/* Общие настройки */}
          <TabPane tab="Общие" key="general">
            <Card title="Основные параметры">
              <Form.Item
                name={['general', 'siteName']}
                label="Название сайта"
                rules={[{ required: true, message: 'Введите название сайта' }]}
              >
                <Input placeholder="Job Scraper" />
              </Form.Item>

              <Form.Item
                name={['general', 'adminEmail']}
                label="Email администратора"
                rules={[
                  { required: true, message: 'Введите email' },
                  { type: 'email', message: 'Введите корректный email' }
                ]}
              >
                <Input placeholder="admin@example.com" />
              </Form.Item>

              <Form.Item
                name={['general', 'timezone']}
                label="Часовой пояс"
                rules={[{ required: true, message: 'Выберите часовой пояс' }]}
              >
                <Select placeholder="Выберите часовой пояс">
                  <Select.Option value="Europe/Moscow">Europe/Moscow</Select.Option>
                  <Select.Option value="Europe/Kiev">Europe/Kiev</Select.Option>
                  <Select.Option value="UTC">UTC</Select.Option>
                  <Select.Option value="America/New_York">America/New_York</Select.Option>
                </Select>
              </Form.Item>

              <Form.Item
                name={['general', 'language']}
                label="Язык интерфейса"
                rules={[{ required: true, message: 'Выберите язык' }]}
              >
                <Select placeholder="Выберите язык">
                  <Select.Option value="ru">Русский</Select.Option>
                  <Select.Option value="en">English</Select.Option>
                </Select>
              </Form.Item>
            </Card>
          </TabPane>

          {/* Настройки парсинга */}
          <TabPane tab="Парсинг" key="scraping">
            <Card title="Параметры парсинга">
              <Form.Item
                name={['scraping', 'defaultDelay']}
                label="Задержка по умолчанию (сек)"
                rules={[{ required: true, message: 'Введите задержку' }]}
              >
                <InputNumber min={1} max={60} style={{ width: '100%' }} />
              </Form.Item>

              <Form.Item
                name={['scraping', 'maxConcurrent']}
                label="Максимум одновременных запросов"
                rules={[{ required: true, message: 'Введите количество' }]}
              >
                <InputNumber min={1} max={20} style={{ width: '100%' }} />
              </Form.Item>

              <Form.Item
                name={['scraping', 'retryAttempts']}
                label="Количество повторных попыток"
                rules={[{ required: true, message: 'Введите количество' }]}
              >
                <InputNumber min={0} max={10} style={{ width: '100%' }} />
              </Form.Item>

              <Form.Item
                name={['scraping', 'timeout']}
                label="Таймаут запроса (сек)"
                rules={[{ required: true, message: 'Введите таймаут' }]}
              >
                <InputNumber min={5} max={300} style={{ width: '100%' }} />
              </Form.Item>

              <Form.Item
                name={['scraping', 'userAgents']}
                label="User-Agent строки (по одной на строку)"
              >
                <TextArea
                  rows={4}
                  placeholder="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36..."
                />
              </Form.Item>

              <Form.Item
                name={['scraping', 'proxies']}
                label="Прокси серверы (по одному на строку)"
              >
                <TextArea
                  rows={4}
                  placeholder="http://proxy1:port&#10;http://proxy2:port"
                />
              </Form.Item>
            </Card>
          </TabPane>

          {/* Уведомления */}
          <TabPane tab="Уведомления" key="notifications">
            <Card title="Настройки уведомлений">
              <Form.Item
                name={['notifications', 'emailEnabled']}
                label="Email уведомления"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>

              <Form.Item
                name={['notifications', 'slackEnabled']}
                label="Slack уведомления"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>

              <Form.Item
                name={['notifications', 'slackWebhook']}
                label="Slack Webhook URL"
              >
                <Input placeholder="https://hooks.slack.com/services/..." />
              </Form.Item>

              <Form.Item
                name={['notifications', 'errorThreshold']}
                label="Порог ошибок для уведомления"
                rules={[{ required: true, message: 'Введите порог' }]}
              >
                <InputNumber min={1} max={100} style={{ width: '100%' }} />
              </Form.Item>

              <Divider />

              <Space>
                <Button
                  icon={<TestOutlined />}
                  onClick={() => testSettingsMutation.mutate('email')}
                  loading={testSettingsMutation.isLoading}
                >
                  Тест Email
                </Button>
                <Button
                  icon={<TestOutlined />}
                  onClick={() => testSettingsMutation.mutate('slack')}
                  loading={testSettingsMutation.isLoading}
                >
                  Тест Slack
                </Button>
              </Space>
            </Card>
          </TabPane>

          {/* База данных */}
          <TabPane tab="База данных" key="database">
            <Card title="Настройки базы данных">
              <Form.Item
                name={['database', 'cleanupEnabled']}
                label="Автоматическая очистка старых данных"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>

              <Form.Item
                name={['database', 'cleanupDays']}
                label="Удалять данные старше (дней)"
                rules={[{ required: true, message: 'Введите количество дней' }]}
              >
                <InputNumber min={1} max={365} style={{ width: '100%' }} />
              </Form.Item>

              <Form.Item
                name={['database', 'backupEnabled']}
                label="Автоматическое резервное копирование"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>

              <Form.Item
                name={['database', 'backupSchedule']}
                label="Расписание резервного копирования"
              >
                <Select placeholder="Выберите расписание">
                  <Select.Option value="daily">Ежедневно</Select.Option>
                  <Select.Option value="weekly">Еженедельно</Select.Option>
                  <Select.Option value="monthly">Ежемесячно</Select.Option>
                </Select>
              </Form.Item>

              <Divider />

              <Button
                icon={<TestOutlined />}
                onClick={() => testSettingsMutation.mutate('database')}
                loading={testSettingsMutation.isLoading}
              >
                Тест подключения к БД
              </Button>
            </Card>
          </TabPane>
        </Tabs>

        {/* Кнопки действий */}
        <Card style={{ marginTop: 16 }}>
          <Space>
            <Button
              type="primary"
              htmlType="submit"
              icon={<SaveOutlined />}
              loading={saveSettingsMutation.isLoading}
              size="large"
            >
              Сохранить настройки
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={handleReset}
              size="large"
            >
              Сбросить
            </Button>
          </Space>
        </Card>
      </Form>
    </div>
  )
}

export default Settings
