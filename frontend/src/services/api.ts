import axios, { AxiosResponse } from 'axios'
import type {
  Job,
  Company,
  JobsResponse,
  CompaniesResponse,
  SearchResponse,
  StatsResponse,
  ScrapeLog,
  TaskStatus,
  JobsParams,
  CompaniesParams,
  SearchParams,
  PaginatedResponse
} from '@/types'

// Создаем экземпляр axios с базовой конфигурацией
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Добавляем API ключ если он есть
const apiKey = import.meta.env.VITE_API_KEY
if (apiKey) {
  api.defaults.headers.common['X-API-KEY'] = apiKey
}

// Интерцептор для обработки ошибок
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

// Утилита для построения query параметров
const buildQueryParams = (params: Record<string, any>): string => {
  const searchParams = new URLSearchParams()
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, String(value))
    }
  })
  
  return searchParams.toString()
}

// API для работы с вакансиями
export const jobsApi = {
  // Получение списка вакансий
  getJobs: async (params: JobsParams = {}): Promise<JobsResponse> => {
    const queryString = buildQueryParams(params)
    const response: AxiosResponse<JobsResponse> = await api.get(`/jobs?${queryString}`)
    return response.data
  },

  // Получение конкретной вакансии
  getJob: async (id: number): Promise<Job> => {
    const response: AxiosResponse<Job> = await api.get(`/jobs/${id}`)
    return response.data
  },

  // Получение статистики по вакансиям
  getJobsStats: async (): Promise<any> => {
    const response = await api.get('/jobs/stats/summary')
    return response.data
  },
}

// API для работы с компаниями
export const companiesApi = {
  // Получение списка компаний
  getCompanies: async (params: CompaniesParams = {}): Promise<CompaniesResponse> => {
    const queryString = buildQueryParams(params)
    const response: AxiosResponse<CompaniesResponse> = await api.get(`/companies?${queryString}`)
    return response.data
  },

  // Получение конкретной компании
  getCompany: async (id: number): Promise<Company> => {
    const response: AxiosResponse<Company> = await api.get(`/companies/${id}`)
    return response.data
  },

  // Получение вакансий компании
  getCompanyJobs: async (id: number, params: { page?: number; size?: number; active_only?: boolean } = {}) => {
    const queryString = buildQueryParams(params)
    const response = await api.get(`/companies/${id}/jobs?${queryString}`)
    return response.data
  },

  // Получение статистики по компаниям
  getCompaniesStats: async (): Promise<any> => {
    const response = await api.get('/companies/stats/summary')
    return response.data
  },
}

// API для поиска
export const searchApi = {
  // Поиск вакансий
  searchJobs: async (params: SearchParams): Promise<SearchResponse> => {
    const queryString = buildQueryParams(params)
    const response: AxiosResponse<SearchResponse> = await api.get(`/search?${queryString}`)
    return response.data
  },

  // Получение предложений для автодополнения
  getSuggestions: async (query: string, type: string = 'all', limit: number = 10) => {
    const response = await api.get(`/search/suggestions?q=${encodeURIComponent(query)}&type=${type}&limit=${limit}`)
    return response.data
  },

  // Получение популярных запросов
  getTrendingSearches: async (period: string = 'week', limit: number = 10) => {
    const response = await api.get(`/search/trending?period=${period}&limit=${limit}`)
    return response.data
  },
}

// API для администрирования
export const adminApi = {
  // Получение общей статистики
  getStats: async (): Promise<StatsResponse> => {
    const response: AxiosResponse<StatsResponse> = await api.get('/admin/stats')
    return response.data
  },

  // Запуск скрапинга
  triggerScrape: async (site: string, maxPages: number = 5) => {
    const response = await api.post('/admin/scrape/trigger', {
      site,
      max_pages: maxPages
    })
    return response.data
  },

  // Получение статуса задачи
  getTaskStatus: async (taskId: string): Promise<TaskStatus> => {
    const response: AxiosResponse<TaskStatus> = await api.get(`/admin/scrape/status/${taskId}`)
    return response.data
  },

  // Получение логов скрапинга
  getScrapeLogs: async (params: {
    page?: number
    size?: number
    site?: string
    status?: string
    date_from?: string
    date_to?: string
  } = {}): Promise<PaginatedResponse<ScrapeLog>> => {
    const queryString = buildQueryParams(params)
    const response = await api.get(`/admin/scrape/logs?${queryString}`)
    return response.data
  },

  // Получение информации о Celery workers
  getCeleryWorkers: async () => {
    const response = await api.get('/admin/celery/workers')
    return response.data
  },

  // Отмена задачи
  revokeTask: async (taskId: string, terminate: boolean = false) => {
    const response = await api.post(`/admin/celery/tasks/${taskId}/revoke?terminate=${terminate}`)
    return response.data
  },

  // Получение статистики базы данных
  getDatabaseStats: async () => {
    const response = await api.get('/admin/database/stats')
    return response.data
  },

  // Переиндексация Elasticsearch
  reindexElasticsearch: async (batchSize: number = 1000, force: boolean = false) => {
    const response = await api.post(`/admin/elasticsearch/reindex?batch_size=${batchSize}&force=${force}`)
    return response.data
  },

  // Получение системной информации
  getSystemInfo: async () => {
    const response = await api.get('/admin/system/info')
    return response.data
  },

  // Очистка старых логов
  cleanupLogs: async (days: number = 30, dryRun: boolean = false) => {
    const response = await api.delete(`/admin/scrape/logs/cleanup?days=${days}&dry_run=${dryRun}`)
    return response.data
  },
}

// API для проверки здоровья системы
export const healthApi = {
  // Проверка здоровья
  getHealth: async () => {
    const response = await api.get('/health')
    return response.data
  },

  // Проверка готовности
  getReadiness: async () => {
    const response = await api.get('/health/ready')
    return response.data
  },

  // Проверка активности
  getLiveness: async () => {
    const response = await api.get('/health/live')
    return response.data
  },
}

export default api
