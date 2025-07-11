import React from 'react'
import { Result, Button } from 'antd'
import { FallbackProps } from 'react-error-boundary'

const ErrorFallback: React.FC<FallbackProps> = ({ error, resetErrorBoundary }) => {
  return (
    <Result
      status="500"
      title="Произошла ошибка"
      subTitle={error.message || 'Что-то пошло не так. Попробуйте обновить страницу.'}
      extra={
        <Button type="primary" onClick={resetErrorBoundary}>
          Попробовать снова
        </Button>
      }
    />
  )
}

export default ErrorFallback
