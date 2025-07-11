import React, { useState } from 'react'
import { Card, Table, Button, Space, Typography, Input, Select, DatePicker, Modal, message, Tabs } from 'antd'
import { 
  SearchOutlined, 
  DeleteOutlined, 
  ExportOutlined,
  ImportOutlined,
  ReloadOutlined,
  EyeOutlined
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from 'react-query'

const { Title, Text } = Typography
const { RangePicker } = DatePicker
const { TabPane } = Tabs

interface Job {
  id: string
  title: string
  company: string
  location: string
  salary?: string
  description: string
  jobUrl: string
  postedDate: string
  createdAt: string
  status: 'new' | 'processed' | 'duplicate'
}

interface Company {
  id: string
  name: string
  website?: string
  description?: string
  jobCount: number
  createdAt: string
}

const DataManagement: React.FC = () => {
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([])
  const [searchText, setSearchText] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [dateRange, setDateRange] = useState<any[]>([])
  const [viewModalVisible, setViewModalVisible] = useState(false)
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const queryClient = useQueryClient()

  // Получение списка вакансий
  const { data: jobs, isLoading: jobsLoading } = useQuery<Job[]>(
    ['jobs', searchText, statusFilter, dateRange],
    async () => {
      const params = new URLSearchParams()
      if (searchText) params.append('search', searchText)
      if (statusFilter) params.append('status', statusFilter)
      if (dateRange.length === 2) {
        params.append('dateFrom', dateRange[0].format('YYYY-MM-DD'))
        params.append('dateTo', dateRange[1].format('YYYY-MM-DD'))
      }
      
      const response = await fetch(`/api/admin/jobs?${params}`)
      return response.json()
    },
    { refetchInterval: 30000 }
  )

  // Получение списка компаний
  const { data: companies, isLoading: companiesLoading } = useQuery<Company[]>(
    'companies',
    async () => {
      const response = await fetch('/api/admin/companies')
      return response.json()
    },
    { refetchInterval: 60000 }
  )

  // Мутация для удаления вакансий
  const deleteJobsMutation = useMutation(
    async (jobIds: string[]) => {
      const response = await fetch('/api/admin/jobs/bulk-delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jobIds })
      })
      if (!response.ok) throw new Error('Failed to delete jobs')
      return response.json()
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('jobs')
        setSelectedRowKeys([])
        message.success('Вакансии удалены успешно')
      },
      onError: () => {
        message.error('Ошибка при удалении вакансий')
      }
    }
  )

  // Мутация для экспорта данных
  const exportDataMutation = useMutation(
    async (format: 'csv' | 'json' | 'xlsx') => {
      const response = await fetch(`/api/admin/export/${format}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          jobIds: selectedRowKeys.length > 0 ? selectedRowKeys : undefined 
        })
      })
      if (!response.ok) throw new Error('Failed to export data')
      
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `jobs_export.${format}`
      a.click()
      window.URL.revokeObjectURL(url)
      
      return true
    },
    {
      onSuccess: () => {
        message.success('Данные экспортированы успешно')
      },
      onError: () => {
        message.error('Ошибка при экспорте данных')
      }
    }
  )

  // Колонки таблицы вакансий
  const jobColumns = [
    {
      title: 'Название',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (text: string, record: Job) => (
        <Button
          type="link"
          onClick={() => {
            setSelectedJob(record)
            setViewModalVisible(true)
          }}
          style={{ padding: 0, height: 'auto' }}
        >
          {text}
        </Button>
      )
    },
    {
      title: 'Компания',
      dataIndex: 'company',
      key: 'company',
      width: 150
    },
    {
      title: 'Локация',
      dataIndex: 'location',
      key: 'location',
      width: 120
    },
    {
      title: 'Зарплата',
      dataIndex: 'salary',
      key: 'salary',
      width: 120,
      render: (salary: string) => salary || '-'
    },
    {
      title: 'Дата публикации',
      dataIndex: 'postedDate',
      key: 'postedDate',
      width: 120,
      render: (date: string) => new Date(date).toLocaleDateString('ru-RU')
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const statusConfig = {
          new: { color: 'blue', text: 'Новая' },
          processed: { color: 'green', text: 'Обработана' },
          duplicate: { color: 'orange', text: 'Дубликат' }
        }
        const config = statusConfig[status as keyof typeof statusConfig]
        return <span style={{ color: config.color }}>{config.text}</span>
      }
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 100,
      render: (record: Job) => (
        <Space>
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => {
              setSelectedJob(record)
              setViewModalVisible(true)
            }}
          >
            Просмотр
          </Button>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => {
              Modal.confirm({
                title: 'Удалить вакансию?',
                content: 'Вы уверены, что хотите удалить эту вакансию?',
                onOk: () => deleteJobsMutation.mutate([record.id])
              })
            }}
          />
        </Space>
      )
    }
  ]

  // Колонки таблицы компаний
  const companyColumns = [
    {
      title: 'Название',
      dataIndex: 'name',
      key: 'name'
    },
    {
      title: 'Сайт',
      dataIndex: 'website',
      key: 'website',
      render: (website: string) => website ? (
        <a href={website} target="_blank" rel="noopener noreferrer">
          {website}
        </a>
      ) : '-'
    },
    {
      title: 'Количество вакансий',
      dataIndex: 'jobCount',
      key: 'jobCount',
      width: 150
    },
    {
      title: 'Дата добавления',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 150,
      render: (date: string) => new Date(date).toLocaleDateString('ru-RU')
    }
  ]

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[]) => {
      setSelectedRowKeys(keys as string[])
    }
  }

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>Управление данными</Title>
        <Text type="secondary">Просмотр и управление собранными данными</Text>
      </div>

      <Tabs defaultActiveKey="jobs">
        <TabPane tab="Вакансии" key="jobs">
          {/* Фильтры */}
          <Card style={{ marginBottom: 16 }}>
            <Space wrap>
              <Input
                placeholder="Поиск по названию или компании"
                prefix={<SearchOutlined />}
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                style={{ width: 250 }}
              />
              <Select
                placeholder="Статус"
                value={statusFilter}
                onChange={setStatusFilter}
                style={{ width: 120 }}
                allowClear
              >
                <Select.Option value="new">Новая</Select.Option>
                <Select.Option value="processed">Обработана</Select.Option>
                <Select.Option value="duplicate">Дубликат</Select.Option>
              </Select>
              <RangePicker
                placeholder={['Дата от', 'Дата до']}
                value={dateRange}
                onChange={setDateRange}
              />
              <Button
                icon={<ReloadOutlined />}
                onClick={() => {
                  setSearchText('')
                  setStatusFilter('')
                  setDateRange([])
                  queryClient.invalidateQueries('jobs')
                }}
              >
                Сбросить
              </Button>
            </Space>
          </Card>

          {/* Действия */}
          <Card
            title={`Вакансии (${jobs?.length || 0})`}
            extra={
              <Space>
                {selectedRowKeys.length > 0 && (
                  <>
                    <Button
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => {
                        Modal.confirm({
                          title: 'Удалить выбранные вакансии?',
                          content: `Вы уверены, что хотите удалить ${selectedRowKeys.length} вакансий?`,
                          onOk: () => deleteJobsMutation.mutate(selectedRowKeys)
                        })
                      }}
                      loading={deleteJobsMutation.isLoading}
                    >
                      Удалить выбранные ({selectedRowKeys.length})
                    </Button>
                  </>
                )}
                <Button
                  icon={<ExportOutlined />}
                  onClick={() => {
                    Modal.confirm({
                      title: 'Экспорт данных',
                      content: 'Выберите формат экспорта:',
                      footer: (
                        <Space>
                          <Button onClick={() => exportDataMutation.mutate('csv')}>
                            CSV
                          </Button>
                          <Button onClick={() => exportDataMutation.mutate('json')}>
                            JSON
                          </Button>
                          <Button onClick={() => exportDataMutation.mutate('xlsx')}>
                            Excel
                          </Button>
                        </Space>
                      )
                    })
                  }}
                  loading={exportDataMutation.isLoading}
                >
                  Экспорт
                </Button>
              </Space>
            }
          >
            <Table
              dataSource={jobs}
              columns={jobColumns}
              loading={jobsLoading}
              rowKey="id"
              rowSelection={rowSelection}
              pagination={{
                pageSize: 20,
                showSizeChanger: true,
                showQuickJumper: true,
                showTotal: (total: number, range: number[]) => 
                  `${range[0]}-${range[1]} из ${total} вакансий`
              }}
              size="small"
              className="admin-table"
            />
          </Card>
        </TabPane>

        <TabPane tab="Компании" key="companies">
          <Card title={`Компании (${companies?.length || 0})`}>
            <Table
              dataSource={companies}
              columns={companyColumns}
              loading={companiesLoading}
              rowKey="id"
              pagination={{ pageSize: 20 }}
              size="small"
              className="admin-table"
            />
          </Card>
        </TabPane>
      </Tabs>

      {/* Модальное окно просмотра вакансии */}
      <Modal
        title="Детали вакансии"
        open={viewModalVisible}
        onCancel={() => setViewModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setViewModalVisible(false)}>
            Закрыть
          </Button>,
          selectedJob && (
            <Button
              key="link"
              type="primary"
              onClick={() => window.open(selectedJob.jobUrl, '_blank')}
            >
              Открыть оригинал
            </Button>
          )
        ]}
        width={800}
      >
        {selectedJob && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <Title level={4}>{selectedJob.title}</Title>
              <Text strong>{selectedJob.company}</Text> • {selectedJob.location}
              {selectedJob.salary && (
                <span> • <Text type="success">{selectedJob.salary}</Text></span>
              )}
            </div>
            
            <div style={{ marginBottom: 16 }}>
              <Text type="secondary">
                Опубликовано: {new Date(selectedJob.postedDate).toLocaleDateString('ru-RU')}
              </Text>
            </div>

            <div style={{ 
              background: '#fafafa', 
              padding: 16, 
              borderRadius: 6,
              whiteSpace: 'pre-wrap',
              maxHeight: 400,
              overflow: 'auto'
            }}>
              {selectedJob.description}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default DataManagement
