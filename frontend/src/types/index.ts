// Основные типы для приложения

export interface Job {
  id: number
  job_title: string
  company_name: string
  location?: string
  description?: string
  salary?: string
  posted_date?: string
  source_site: string
  remote_allowed?: boolean
  employment_type?: string
  experience_level?: string
  skills?: string[]
  created_at: string
  updated_at: string
}

export interface Company {
  id: number
  name: string
  website?: string
  description?: string
  location?: string
  industry?: string
  size?: string
  logo_url?: string
  jobs_count: number
  created_at: string
  updated_at: string
}

export interface SearchResult {
  id: number
  job_title: string
  company_name: string
  location?: string
  description?: string
  salary?: string
  posted_date?: string
  source_site: string
  score: number
}

export interface SearchResponse {
  results: SearchResult[]
  total: number
  query: string
  took: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
  has_next: boolean
  has_prev: boolean
}

export interface JobsResponse extends PaginatedResponse<Job> {}
export interface CompaniesResponse extends PaginatedResponse<Company> {}

export interface ScrapeLog {
  id: number
  site: string
  status: 'running' | 'completed' | 'failed'
  start_time: string
  end_time?: string
  duration_seconds?: number
  jobs_scraped: number
  errors_count: number
  error_message?: string
}

export interface StatsResponse {
  total_jobs: number
  total_companies: number
  jobs_last_24h: number
  sites_stats: Array<{
    site: string
    jobs_count: number
  }>
  scraping_stats: {
    total_scrapes: number
    successful_scrapes: number
    failed_scrapes: number
    success_rate: number
    avg_duration_seconds: number
  }
  top_companies: Array<{
    name: string
    jobs_count: number
  }>
  generated_at: string
}

export interface TaskStatus {
  task_id: string
  status: string
  result?: any
  error?: string
  created_at: string
}

export interface ApiError {
  detail: string
  status_code?: number
}

// Фильтры для поиска
export interface JobFilters {
  keyword?: string
  location?: string
  company?: string
  employment_type?: string
  experience_level?: string
  remote_allowed?: boolean
  source_site?: string
  date_from?: string
  date_to?: string
  salary_min?: number
  salary_max?: number
}

export interface SearchFilters extends JobFilters {
  use_elasticsearch?: boolean
}

// Параметры пагинации
export interface PaginationParams {
  page?: number
  size?: number
}

// Параметры сортировки
export interface SortParams {
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

// Комбинированные параметры для запросов
export interface JobsParams extends JobFilters, PaginationParams, SortParams {}
export interface CompaniesParams extends PaginationParams, SortParams {
  name?: string
  industry?: string
  location?: string
  company_size?: string
  has_jobs?: boolean
}
export interface SearchParams extends SearchFilters, PaginationParams {
  q: string
  from?: number
}
